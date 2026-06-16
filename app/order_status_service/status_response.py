from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from order_status_service.exceptions import DocumentDateNotFound, OrderIdNotFound
from order_status_service.transport.saferoute_delivery import build_saferoute_delivery_response_from_result
from order_status_service.utils import business_today, date_from_iso_datetime, normalize_track_number

TRANSPORT_LOOKUP_AFTER = timedelta(hours=72)


def build_main_endpoint_response(
    service: PlatformAdminService,
    document_store: DocumentStore | None,
    raw_track_number: str,
    by_date: str | None = None,
) -> dict:
    order_number = normalize_track_number(raw_track_number)
    if not order_number:
        raise OrderIdNotFound("Track number does not contain an order number")

    status_payload = service.get_order_production_history_by_track_number(raw_track_number, by_date=by_date)
    resolved_order_number = status_payload.get("order_number") or order_number
    status = status_payload.get("status")
    changed_at = status_payload.get("changed_at")
    platform_status = status_payload.get("platform_status")
    payment_status = status_payload.get("payment_status")
    base_payload = {
        "order_status": platform_status,
        "payment_status": payment_status,
    }

    transport_payload = build_transport_lookup_response(
        service=service,
        status_payload=status_payload,
        raw_track_number=raw_track_number,
        resolved_order_number=resolved_order_number,
    )
    if transport_payload:
        return {
            **transport_payload,
            "payment_status": payment_status,
            "erp_order_status": platform_status,
        }

    if payment_status == "unpaid":
        return {
            "type": "unpaid",
            "date": None,
            **base_payload,
        }
    if platform_status == "new":
        return {
            "type": "new",
            "date": None,
            **base_payload,
        }
    if platform_status == "received":
        transport_payload = build_transport_lookup_response(
            service=service,
            status_payload=status_payload,
            raw_track_number=raw_track_number,
            resolved_order_number=resolved_order_number,
            force=True,
            lookup_reason="erp_received",
        )
        if transport_payload:
            return {
                **transport_payload,
                "payment_status": payment_status,
                "erp_order_status": platform_status,
            }
        return {
            "type": "received",
            "date": None,
            **base_payload,
        }
    if status != "post_production_finished":
        return {
            "type": "in_work",
            "date": None,
            **base_payload,
        }

    if not document_store or not document_store.enabled:
        raise RuntimeError("Postgres is not configured")

    status_date = date_from_iso_datetime(changed_at)
    if not status_date:
        return transport_response_or_raise(
            service=service,
            status_payload=status_payload,
            raw_track_number=raw_track_number,
            resolved_order_number=resolved_order_number,
            payment_status=payment_status,
            platform_status=platform_status,
            error=DocumentDateNotFound("Production status date is missing"),
        )

    if not document_store.has_delivery_records_for_date(status_date):
        return transport_response_or_raise(
            service=service,
            status_payload=status_payload,
            raw_track_number=raw_track_number,
            resolved_order_number=resolved_order_number,
            payment_status=payment_status,
            platform_status=platform_status,
            error=DocumentDateNotFound(f"No delivery records for {status_date.isoformat()}"),
        )

    same_day_record = document_store.find_delivery_record(status_date, resolved_order_number)
    if same_day_record:
        return {
            "type": "shipped",
            "date": status_date.isoformat(),
            **base_payload,
        }

    next_date = status_date + timedelta(days=1)
    if not document_store.has_delivery_records_for_date(next_date):
        if next_date < business_today():
            return transport_response_or_raise(
                service=service,
                status_payload=status_payload,
                raw_track_number=raw_track_number,
                resolved_order_number=resolved_order_number,
                payment_status=payment_status,
                platform_status=platform_status,
                error=DocumentDateNotFound(f"No delivery records for past date {next_date.isoformat()}"),
            )
        return {
            "type": "tommorow",
            "date": next_date.isoformat(),
            **base_payload,
        }

    next_day_record = document_store.find_delivery_record(next_date, resolved_order_number)
    if next_day_record:
        return {
            "type": "shipped",
            "date": next_date.isoformat(),
            **base_payload,
        }

    return transport_response_or_raise(
        service=service,
        status_payload=status_payload,
        raw_track_number=raw_track_number,
        resolved_order_number=resolved_order_number,
        payment_status=payment_status,
        platform_status=platform_status,
        error=DocumentDateNotFound(f"Order {resolved_order_number} is absent in delivery records"),
    )


def build_transport_lookup_response(
    service: PlatformAdminService,
    status_payload: dict,
    raw_track_number: str,
    resolved_order_number: str,
    force: bool = False,
    lookup_reason: str | None = None,
) -> dict | None:
    if not service.transport_adapter:
        return None
    if force and transport_kind(status_payload) not in {"saferoute", "fivepost", "yandex"}:
        return None
    if not force and not should_lookup_transport_status(status_payload):
        return None

    kind = transport_kind(status_payload)
    for number in transport_lookup_numbers(status_payload, raw_track_number, resolved_order_number):
        result = find_transport_by_kind(service.transport_adapter, kind, number)
        if result:
            response = build_saferoute_delivery_response_from_result(result)
            response["transport_lookup"] = True
            response["transport_lookup_reason"] = lookup_reason or ("forced_fallback" if force else "after_72h")
            response["transport_stage"] = response.get("current_delivery_status")
            response["transport_status_code"] = response.get("current_delivery_status_code")
            response["transport_status_date"] = response.get("current_delivery_status_date")
            response["tracking_available"] = True
            response["platform_status_updated_at"] = status_payload.get("platform_status_updated_at")
            if response.get("type") == "shipped":
                response["type"] = "transport_status"
            return response
    return None


def find_transport_by_kind(adapter, kind: str | None, number: str):
    if kind:
        for candidate in getattr(adapter, "adapters", []):
            if getattr(candidate, "name", None) == kind:
                return candidate.find_by_number(number)
    return adapter.find_by_number(number)


def transport_response_or_raise(
    service: PlatformAdminService,
    status_payload: dict,
    raw_track_number: str,
    resolved_order_number: str,
    payment_status: str | None,
    platform_status: str | None,
    error: DocumentDateNotFound,
) -> dict:
    transport_payload = build_transport_lookup_response(
        service=service,
        status_payload=status_payload,
        raw_track_number=raw_track_number,
        resolved_order_number=resolved_order_number,
        force=True,
    )
    if transport_payload:
        return {
            **transport_payload,
            "payment_status": payment_status,
            "erp_order_status": platform_status,
        }
    raise error


def should_lookup_transport_status(status_payload: dict) -> bool:
    if status_payload.get("platform_status") != "sent":
        return False
    if transport_kind(status_payload) not in {"saferoute", "fivepost", "yandex"}:
        return False

    changed_at = status_payload.get("platform_status_updated_at") or status_payload.get("changed_at")
    changed_datetime = datetime_from_platform(changed_at)
    if not changed_datetime:
        return False
    now = datetime.now(timezone(timedelta(hours=3)))
    return now - changed_datetime.astimezone(now.tzinfo) >= TRANSPORT_LOOKUP_AFTER


def transport_kind(status_payload: dict) -> str | None:
    delivery_system_id = str(status_payload.get("delivery_system_id") or "").strip()
    delivery_system_type = str(status_payload.get("delivery_system_type") or "").strip().lower()
    delivery_system_name = str(status_payload.get("delivery_system_name") or "").strip().lower()
    haystack = " ".join(
        str(status_payload.get(key) or "")
        for key in ("delivery_system_type", "delivery_system_name")
    ).lower()
    if "safe_route" in haystack or "saferoute" in haystack:
        return "saferoute"
    if "five_post" in haystack or "fivepost" in haystack or "5post" in haystack:
        return "fivepost"
    if (
        delivery_system_id == "1407"
        or delivery_system_type == "yandex_to_point"
        or delivery_system_name == "yandex to point"
        or "яндекс" in haystack
        or "yandex" in haystack
    ):
        return "yandex"
    return None


def transport_lookup_numbers(
    status_payload: dict,
    raw_track_number: str,
    resolved_order_number: str,
) -> list[str]:
    tracking_number = status_payload.get("tracking_number")
    delivery_shipment_id = status_payload.get("delivery_shipment_id")
    tracking_number_from_link = tracking_number_from_url(status_payload.get("delivery_shipment_tracking_link"))
    kind = transport_kind(status_payload)
    if kind == "fivepost":
        values = [tracking_number, tracking_number_from_link, raw_track_number, resolved_order_number]
    elif kind == "yandex":
        values = [
            delivery_shipment_id,
            tracking_number,
            tracking_number_from_link,
            raw_track_number,
            resolved_order_number,
        ]
    else:
        values = [raw_track_number, tracking_number, tracking_number_from_link, resolved_order_number]
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        number = str(value or "").strip()
        if not number or number in seen:
            continue
        seen.add(number)
        result.append(number)
    return result


def tracking_number_from_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(str(value))
    query = parse_qs(parsed.query)
    for key in ("id", "track", "tracking", "order"):
        values = query.get(key)
        if values and str(values[0]).strip():
            return str(values[0]).strip()
    return None


def datetime_from_platform(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    normalized = normalized.replace(" ", "T", 1)
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    if len(normalized) >= 3 and normalized[-3] in {"+", "-"}:
        normalized = f"{normalized}:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if not parsed.tzinfo:
        parsed = parsed.replace(tzinfo=timezone(timedelta(hours=3)))
    return parsed

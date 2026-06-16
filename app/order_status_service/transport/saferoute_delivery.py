from __future__ import annotations

from typing import TYPE_CHECKING

from order_status_service.transport.adapters import TransportLookupResult
from order_status_service.utils import date_from_iso_datetime

if TYPE_CHECKING:
    from order_status_service.transport.adapters import TransportAdapter


SAFEROUTE_STATUS_LABELS = {
    "10": "Заказ отменен до отгрузки на доставку",
    "11": "Черновик",
    "12": "Подтвержден",
    "13": "Готов к отгрузке",
    "14": "Создан в службе доставки",
    "15": "Зарегистрирован в службе доставки",
    "30": "Зарегистрирован в компании сортировки",
    "31": "Принят на сортировке по акту",
    "311": "Принят на сортировке",
    "312": "Подготовлен к отгрузке",
    "32": "Передан в компанию доставки",
    "33": "Передан на возврат",
    "34": "Утерян на сортировке",
    "35": "Принят на сортировке частично",
    "41": "Принят компанией доставки",
    "411": "В пути",
    "412": "В городе получателя",
    "42": "На ПВЗ",
    "43": "Передан курьеру для доставки",
    "44": "Заказ вручен получателю",
    "45": "Утерян компанией доставки",
    "46": "Перенесена дата доставки",
    "461": "Отказ до вручения",
    "462": "Отказ при вручении",
    "47": "Частично вручен",
    "51": "Передан на возврат",
    "52": "Возвращен на сортировку",
    "61": "Принят на сортировку для возврата",
    "62": "Передан в компанию возврата",
    "63": "Утерян на сортировке",
}

SAFEROUTE_RECEIVED_CODES = {"44", "47"}
SAFEROUTE_SHIPPED_CODES = {"31", "311", "312", "32", "41", "411", "412", "42", "43", "46"}
SAFEROUTE_TRANSFER_CODES = {"32", "41", "411"}
YANDEX_RECEIVED_CODES = {"DELIVERED", "DELIVERED_FINISH"}
YANDEX_RECEIVED_CODES |= {
    "DELIVERY_DELIVERED",
    "DELIVERY_TRANSMITTED_TO_RECIPIENT",
    "PICKUP_POINT_DELIVERED",
    "PICKUP_POINT_TRANSMITTED_TO_RECIPIENT",
}
YANDEX_SHIPPED_CODES = {
    "NEW",
    "ESTIMATING",
    "READY_FOR_APPROVAL",
    "ACCEPTED",
    "PERFORMER_LOOKUP",
    "PERFORMER_DRAFT",
    "PERFORMER_FOUND",
    "PICKUP_ARRIVED",
    "READY_FOR_PICKUP_CONFIRMATION",
    "PICKUPED",
    "DELIVERY_ARRIVED",
    "READY_FOR_DELIVERY_CONFIRMATION",
    "PAY_WAITING",
}
YANDEX_SHIPPED_CODES |= {
    "DRAFT",
    "VALIDATING",
    "CREATED",
    "SENDER_SENT",
    "SENDER_WAIT_FULFILLMENT",
    "SORTING_CENTER_PREPARED",
    "SORTING_CENTER_TRANSMITTED",
    "SORTING_CENTER_CREATED",
    "SORTING_CENTER_LOADED",
    "SORTING_CENTER_AT_START",
    "SORTING_CENTER_TRANSMITTED_TO_RECIPIENT",
    "DELIVERY_LOADED",
    "DELIVERY_AT_START",
    "DELIVERY_AT_START_SORT",
    "DELIVERY_TRANSPORTATION",
    "DELIVERY_ARRIVED",
    "DELIVERY_UPDATED_BY_SHOP",
    "RECIPIENT_PICKUP_POINT",
    "RETURN_READY_FOR_PICKUP",
}
TRANSPORT_RECEIVED_CODES = SAFEROUTE_RECEIVED_CODES | {"DELIVERED", "DONE", "RECEIVED"} | YANDEX_RECEIVED_CODES
TRANSPORT_SHIPPED_CODES = (
    SAFEROUTE_SHIPPED_CODES | {"APPROVED", "CREATED", "IN_DELIVERY", "IN_PROCESS", "NEW"} | YANDEX_SHIPPED_CODES
)
FIVEPOST_STATUS_LABELS = {
    "NEW": "Новый",
    "CREATED": "Создан",
    "APPROVED": "Подтвержден",
    "IN_PROCESS": "В обработке",
    "IN_DELIVERY": "В доставке",
    "DELIVERED": "Доставлен",
    "DONE": "Выдан",
    "RECEIVED": "Получен",
    "CANCELLED": "Отменен",
    "UNCLAIMED": "Не востребован",
    "REJECTED": "Отклонен",
}


def build_saferoute_delivery_response(adapter: TransportAdapter | None, track_number: str) -> dict | None:
    if not adapter:
        return None

    result = adapter.find_by_number(track_number)
    if not result:
        return None

    return build_saferoute_delivery_response_from_result(result)


def build_saferoute_delivery_response_from_result(result: TransportLookupResult) -> dict:
    payload = result.payload
    order = payload.get("order") if isinstance(payload.get("order"), dict) else {}
    history_items = _history_items(payload)
    latest_status = history_items[0] if history_items else {}
    current_code = (
        result.delivery_status_code
        or str(latest_status.get("code") or latest_status.get("statusCode") or "").strip()
    )
    current_date = str(
        latest_status.get("date")
        or latest_status.get("changed_at")
        or latest_status.get("changeDate")
        or latest_status.get("statusAssignmentDate")
        or ""
    ).strip()
    transfer_status = next(
        (
            item
            for item in history_items
            if str(item.get("code") or "").strip() in SAFEROUTE_TRANSFER_CODES
        ),
        None,
    )
    transfer_date = str((transfer_status or {}).get("date") or "").strip()
    result_type = _result_type(current_code, result.adapter, result.delivery_status_label)

    delivery = payload.get("delivery") if isinstance(payload.get("delivery"), dict) else {}
    delivery_company = delivery.get("company") if isinstance(delivery.get("company"), dict) else {}
    delivery_date = delivery.get("date") if isinstance(delivery.get("date"), dict) else {}
    current_status_label = _status_label(result.adapter, current_code, result.delivery_status_label)
    current_reason, current_reason_text = _current_yandex_reason(result.adapter, current_code, latest_status, history_items)
    response_date_raw = current_date if result_type == "received" else transfer_date or current_date
    response_date = date_from_iso_datetime(response_date_raw)
    transport_id = payload.get("id") or order.get("orderId") or order.get("id")

    return {
        "track_number": result.lookup_number,
        "type": result_type,
        "date": response_date.isoformat() if response_date else None,
        "order_status": current_status_label,
        "payment_status": None,
        "source": f"{result.adapter}_orders",
        "transport_id": transport_id,
        "saferoute_id": transport_id if result.adapter == "saferoute" else None,
        "cms_id": payload.get("cmsId") or payload.get("cms_id") or order.get("senderOrderId") or result.erp_order_number,
        "carrier_track_number": result.carrier_track_number,
        "tracking_url": payload.get("trackingUrl") or payload.get("tracking_url") or order.get("trackingUrl"),
        "delivery_company": delivery_company.get("name"),
        "current_delivery_status": current_status_label,
        "current_delivery_status_code": current_code or None,
        "current_delivery_status_date": current_date or None,
        "current_delivery_status_raw": latest_status.get("rawStatusName"),
        "current_delivery_status_group": latest_status.get("statusGroup"),
        "current_delivery_status_kind": latest_status.get("statusKind"),
        "current_delivery_reason": current_reason,
        "current_delivery_reason_text": current_reason_text,
        "planned_delivery_date": delivery_date.get("from") or delivery_date.get("to"),
        "reason": f"found_in_{result.adapter}_orders",
    }


def _history_items(payload: dict) -> list[dict]:
    history = payload.get("statusHistory") or payload.get("status_history") or payload.get("history") or []
    items = [item for item in history if isinstance(item, dict)]
    if any(_history_date_value(item) for item in items):
        return sorted(items, key=_history_date_value, reverse=True)
    return items


def _history_date_value(item: dict) -> str:
    for key in ("date", "changed_at", "changeDate", "statusAssignmentDate", "createdAt", "created"):
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _current_yandex_reason(
    adapter: str,
    current_code: str,
    latest_status: dict,
    history_items: list[dict],
) -> tuple[str | None, str | None]:
    reason = latest_status.get("reason")
    reason_text = latest_status.get("reasonText")
    if adapter != "yandex" or reason or not str(current_code or "").upper().startswith("RETURN_"):
        return reason, reason_text

    for item in history_items:
        if str(item.get("code") or "").upper() == "CANCELLED" and item.get("reason"):
            return item.get("reason"), item.get("reasonText")
    return None, None


def _result_type(current_code: str, adapter: str = "", provided_label: str | None = None) -> str:
    normalized_code = current_code.upper()
    if normalized_code in TRANSPORT_RECEIVED_CODES:
        return "received"
    if normalized_code in TRANSPORT_SHIPPED_CODES:
        return "shipped"
    if adapter == "yandex" and provided_label and provided_label != current_code:
        return "shipped"
    return "unknown"


def _status_label(adapter: str, current_code: str, provided_label: str | None) -> str | None:
    normalized_code = current_code.upper()
    if adapter == "fivepost":
        return provided_label or FIVEPOST_STATUS_LABELS.get(normalized_code) or current_code or None
    return provided_label or SAFEROUTE_STATUS_LABELS.get(current_code) or current_code or None

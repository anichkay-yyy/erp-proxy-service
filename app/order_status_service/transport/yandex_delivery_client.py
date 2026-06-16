import requests

from order_status_service.config import YANDEX_DELIVERY_API_BASE_URL
from order_status_service.transport.adapters import TransportLookupResult
from order_status_service.transport.yandex_status_lookup import lookup_yandex_status
from order_status_service.utils import normalize_track_number


YANDEX_STATUS_LABELS = {
    "new": "Заявка создана в Яндекс Доставке",
    "accepted": "Заявка подтверждена",
    "performer_found": "Курьер назначен",
    "pickuped": "Отправление передано курьеру",
    "delivery_arrived": "Курьер прибыл к получателю",
    "delivered": "Отправление передано получателю",
    "delivered_finish": "Заказ доставлен получателю",
    "cancelled": "Доставка отменена",
    "DRAFT": "Заявка создана в Яндекс Доставке",
    "VALIDATING": "Заявка проверяется",
    "CREATED": "Заявка создана в Яндекс Доставке",
    "SENDER_SENT": "Заказ передан в Яндекс Доставку",
    "SENDER_WAIT_FULFILLMENT": "Ожидается обработка отправления",
    "SORTING_CENTER_PREPARED": "Отправление готовится к сортировке",
    "SORTING_CENTER_TRANSMITTED": "Отправление передано на сортировку",
    "SORTING_CENTER_CREATED": "Отправление принято сортировочным центром",
    "SORTING_CENTER_LOADED": "Отправление загружено для перевозки",
    "SORTING_CENTER_AT_START": "Отправление находится на сортировочном центре",
    "SORTING_CENTER_TRANSMITTED_TO_RECIPIENT": "Отправление передано в доставку",
    "DELIVERY_LOADED": "Отправление загружено в доставку",
    "DELIVERY_AT_START": "Отправление находится в службе доставки",
    "DELIVERY_AT_START_SORT": "Отправление сортируется в службе доставки",
    "DELIVERY_TRANSPORTATION": "Отправление транспортируется",
    "DELIVERY_ARRIVED": "Отправление прибыло в город получателя",
    "DELIVERY_TRANSMITTED_TO_RECIPIENT": "Отправление передано получателю",
    "DELIVERY_DELIVERED": "Заказ доставлен получателю",
    "RECIPIENT_PICKUP_POINT": "Заказ находится в пункте выдачи",
    "PICKUP_POINT_TRANSMITTED_TO_RECIPIENT": "Заказ выдан получателю",
    "PICKUP_POINT_DELIVERED": "Заказ доставлен получателю",
    "DELIVERY_UPDATED_BY_SHOP": "Статус доставки обновлен магазином",
    "RETURN_READY_FOR_PICKUP": "Возврат готов к получению",
}


class YandexDeliveryClient:
    name = "yandex"

    def __init__(
        self,
        base_url: str = YANDEX_DELIVERY_API_BASE_URL,
        oauth_token: str | None = None,
        timeout: int = 15,
    ):
        self.base_url = base_url.rstrip("/")
        self.oauth_token = str(oauth_token or "").strip()
        self.timeout = timeout
        self.session = requests.Session()

    def has_credentials(self) -> bool:
        return bool(self.oauth_token)

    def find_by_number(self, number: str) -> TransportLookupResult | None:
        lookup_number = str(number or "").strip()
        if not lookup_number or not self.has_credentials():
            return None

        for request_id in self._request_id_variants(lookup_number):
            payload = self._find_platform_request(request_id=request_id)
            if payload:
                return self._build_platform_result(lookup_number, payload)

        for request_code in self._request_code_variants(lookup_number):
            payload = self._find_platform_request(request_code=request_code)
            if payload:
                return self._build_platform_result(lookup_number, payload)

        for claim_id in self._claim_id_variants(lookup_number):
            payload = self._find_express_claim(claim_id)
            if payload:
                return self._build_express_result(lookup_number, payload)

        for external_order_id in self._request_code_variants(lookup_number):
            payload = self._find_express_by_external_order_id(external_order_id)
            if payload:
                return self._build_express_result(lookup_number, payload)

        return None

    def _find_platform_request(self, request_id: str | None = None, request_code: str | None = None) -> dict | None:
        params = {"slim": "true"}
        if request_id:
            params["request_id"] = request_id
        elif request_code:
            params["request_code"] = request_code
        else:
            return None

        info = self._get_optional("/api/b2b/platform/request/info", params=params)
        if not info:
            return None

        request_id = str(info.get("request_id") or request_id or "").strip()
        history = self._get_optional("/api/b2b/platform/request/history", params={"request_id": request_id})
        if isinstance(history, dict):
            info["history"] = history
        return info

    def _find_express_claim(self, claim_id: str) -> dict | None:
        claim = self._post_optional("/b2b/cargo/integration/v2/claims/info", params={"claim_id": claim_id})
        if not claim:
            return None
        return self._enrich_express_claim(claim)

    def _find_express_by_external_order_id(self, external_order_id: str) -> dict | None:
        payload = self._post_optional(
            "/b2b/cargo/integration/v2/claims/search",
            json={"offset": 0, "limit": 20, "external_order_id": external_order_id},
        )
        claims = payload.get("claims") if isinstance(payload, dict) else None
        if not isinstance(claims, list) or not claims:
            return None

        claim = next((item for item in claims if isinstance(item, dict)), {})
        claim_id = str(claim.get("id") or "").strip()
        if claim_id:
            details = self._post_optional("/b2b/cargo/integration/v2/claims/info", params={"claim_id": claim_id})
            if details:
                claim = details
        return self._enrich_express_claim(claim)

    def _enrich_express_claim(self, claim: dict) -> dict:
        claim_id = str(claim.get("id") or "").strip()
        status = str(claim.get("status") or "").strip()
        updated_ts = str(claim.get("updated_ts") or claim.get("created_ts") or "").strip()
        tracking_links = self._express_tracking_links(claim_id) if claim_id else None
        payload = {
            "id": claim_id or None,
            "cmsId": self._erp_order_number_from_express_claim(claim),
            "claim": claim,
            "statusHistory": [
                {"code": status, "date": updated_ts, "statusName": self._label(status, claim.get("description"))}
            ]
            if status
            else [],
            "delivery": {"company": {"name": "Яндекс Доставка"}},
        }
        tracking_url = self._express_tracking_url(tracking_links)
        if tracking_url:
            payload["trackingUrl"] = tracking_url
        return payload

    def _build_platform_result(self, lookup_number: str, payload: dict) -> TransportLookupResult:
        status = self._platform_status(payload)
        reason = self._platform_reason(payload)
        lookup = lookup_yandex_status(status, reason)
        return TransportLookupResult(
            adapter=self.name,
            lookup_number=lookup_number,
            payload=self._platform_payload(payload, lookup_number),
            erp_order_number=self._erp_order_number_from_platform(payload, lookup_number),
            carrier_track_number=self._platform_track_number(payload),
            delivery_status_code=status or None,
            delivery_status_label=lookup.get("stage") or self._platform_status_label(payload),
        )

    def _build_express_result(self, lookup_number: str, payload: dict) -> TransportLookupResult:
        claim = payload.get("claim") if isinstance(payload.get("claim"), dict) else {}
        status = str(claim.get("status") or "").strip()
        return TransportLookupResult(
            adapter=self.name,
            lookup_number=lookup_number,
            payload=payload,
            erp_order_number=self._erp_order_number_from_express_claim(claim),
            carrier_track_number=self._express_track_number(claim, payload),
            delivery_status_code=status or None,
            delivery_status_label=self._label(status, claim.get("description")) if status else None,
        )

    def _platform_payload(self, payload: dict, lookup_number: str) -> dict:
        history_items = self._platform_history_items(payload)
        status = self._platform_status(payload)
        reason = self._platform_reason(payload)
        changed_at = self._platform_changed_at(payload)
        if not history_items and status:
            lookup = lookup_yandex_status(status, reason)
            history_items = [
                {
                    "code": status,
                    "date": changed_at,
                    "statusName": lookup.get("stage") or self._platform_status_label(payload),
                    "rawStatusName": self._platform_status_label(payload),
                    "statusGroup": lookup.get("stage"),
                    "statusKind": lookup.get("kind"),
                    "reason": lookup.get("reason"),
                    "reasonText": lookup.get("reason_text"),
                }
            ]

        result = {
            "id": payload.get("request_id"),
            "cmsId": self._erp_order_number_from_platform(payload, lookup_number),
            "request": payload,
            "statusHistory": history_items,
            "delivery": {"company": {"name": "Яндекс Доставка"}},
        }
        tracking_url = payload.get("sharing_url") or payload.get("tracking_url") or payload.get("trackingUrl")
        if tracking_url:
            result["trackingUrl"] = tracking_url
        return result

    @staticmethod
    def _platform_history_items(payload: dict) -> list[dict]:
        history = payload.get("history") if isinstance(payload.get("history"), dict) else {}
        items = history.get("state_history") if isinstance(history.get("state_history"), list) else []
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "").strip()
            reason = str(item.get("reason") or "").strip()
            lookup = lookup_yandex_status(status, reason)
            result.append(
                {
                    "code": status,
                    "date": item.get("updated_at") or item.get("created_at") or item.get("datetime") or item.get("timestamp_utc"),
                    "statusName": lookup.get("stage") or YandexDeliveryClient._label(status, item.get("description")),
                    "rawStatusName": YandexDeliveryClient._label(status, item.get("description")),
                    "statusGroup": lookup.get("stage"),
                    "statusKind": lookup.get("kind"),
                    "reason": lookup.get("reason"),
                    "reasonText": lookup.get("reason_text"),
                }
            )
        return result

    @staticmethod
    def _platform_status(payload: dict) -> str:
        state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
        return str(state.get("status") or payload.get("status") or "").strip()

    @staticmethod
    def _platform_reason(payload: dict) -> str | None:
        state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
        reason = state.get("reason") or payload.get("reason")
        return str(reason).strip() if reason else None

    @staticmethod
    def _platform_changed_at(payload: dict) -> str | None:
        state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
        return (
            state.get("updated_at")
            or state.get("created_at")
            or state.get("timestamp")
            or payload.get("updated_at")
            or payload.get("created_at")
        )

    @staticmethod
    def _platform_status_label(payload: dict) -> str | None:
        state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
        status = str(state.get("status") or payload.get("status") or "").strip()
        return YandexDeliveryClient._label(status, state.get("description") or payload.get("description"))

    @staticmethod
    def _label(status: str, description: object = None) -> str | None:
        raw_description = str(description or "").strip()
        if raw_description:
            return raw_description
        return YANDEX_STATUS_LABELS.get(status, status) if status else None

    @staticmethod
    def _erp_order_number_from_platform(payload: dict, lookup_number: str) -> str | None:
        for key in ("request_code", "external_order_id", "operator_request_id"):
            normalized = normalize_track_number(str(payload.get(key) or ""))
            if normalized:
                return normalized
        return normalize_track_number(lookup_number)

    @staticmethod
    def _platform_track_number(payload: dict) -> str | None:
        for key in ("courier_order_id", "request_id", "tracking_number", "track_number"):
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    @staticmethod
    def _erp_order_number_from_express_claim(claim: dict) -> str | None:
        for key in ("external_order_id", "external_id"):
            normalized = normalize_track_number(str(claim.get(key) or ""))
            if normalized:
                return normalized
        for item in claim.get("items") or []:
            if isinstance(item, dict):
                normalized = normalize_track_number(str(item.get("extra_id") or ""))
                if normalized:
                    return normalized
        return None

    @staticmethod
    def _express_track_number(claim: dict, payload: dict) -> str | None:
        for source in (claim, payload):
            for key in ("tracking_number", "track_number", "id"):
                value = source.get(key)
                if value is not None and str(value).strip():
                    return str(value).strip()
        return None

    def _express_tracking_links(self, claim_id: str) -> dict | None:
        return self._get_optional("/b2b/cargo/integration/v2/claims/tracking-links", params={"claim_id": claim_id})

    @staticmethod
    def _express_tracking_url(tracking_links: dict | None) -> str | None:
        points = tracking_links.get("route_points") if isinstance(tracking_links, dict) else None
        if not isinstance(points, list):
            return None
        for point in points:
            if isinstance(point, dict) and point.get("sharing_link"):
                return str(point["sharing_link"]).strip()
        return None

    @staticmethod
    def _request_id_variants(number: str) -> list[str]:
        value = str(number or "").strip()
        if len(value) >= 24 and "-" in value:
            return [value]
        return []

    @staticmethod
    def _claim_id_variants(number: str) -> list[str]:
        value = str(number or "").strip()
        if len(value) >= 32:
            return YandexDeliveryClient._unique([value, value.split("-", 1)[0]])
        return []

    @staticmethod
    def _request_code_variants(number: str) -> list[str]:
        value = str(number or "").strip()
        normalized = normalize_track_number(value)
        return YandexDeliveryClient._unique([value, normalized])

    @staticmethod
    def _unique(values: list[str | None]) -> list[str]:
        result = []
        seen = set()
        for value in values:
            item = str(value or "").strip()
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    def _get_optional(self, path: str, params: dict | None = None) -> dict | None:
        try:
            response = self.session.get(
                f"{self.base_url}{path}",
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException:
            return None
        return self._json_or_none(response)

    def _post_optional(self, path: str, params: dict | None = None, json: dict | None = None) -> dict | None:
        try:
            response = self.session.post(
                f"{self.base_url}{path}",
                params=params,
                json=json,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException:
            return None
        return self._json_or_none(response)

    @staticmethod
    def _json_or_none(response) -> dict | None:
        if response.status_code >= 400:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    def _headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Accept-Language": "ru-RU",
            "Authorization": f"Bearer {self.oauth_token}",
            "Content-Type": "application/json",
        }

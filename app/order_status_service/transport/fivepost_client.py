import requests
from urllib.parse import quote

from order_status_service.config import FIVEPOST_API_BASE_URL
from order_status_service.transport.adapters import TransportLookupResult
from order_status_service.utils import normalize_track_number


class FivePostClient:
    name = "fivepost"

    def __init__(
        self,
        base_url: str = FIVEPOST_API_BASE_URL,
        login: str | None = None,
        password: str | None = None,
        timeout: int = 15,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_v1_base_url = f"{self.base_url}/partners-portal/api/v1"
        self.auth_base_url = f"{self.base_url}/partners-portal-auth/api/v2"
        self.login_name = str(login or "").strip()
        self.password = str(password or "").strip()
        self.timeout = timeout
        self.session = requests.Session()
        self.token = None

    def has_credentials(self) -> bool:
        return bool(self.login_name and self.password)

    def login(self) -> None:
        if not self.has_credentials():
            raise RuntimeError("5post credentials are not configured")

        response = self.session.post(
            f"{self.auth_base_url}/auth",
            json={"login": self.login_name, "password": self.password},
            headers=self._headers(authorized=False),
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("jwt") or payload.get("token") or payload.get("access_token")
        if not token:
            raise RuntimeError("5post auth response does not contain token")
        self.token = str(token)

    def ensure_authenticated(self) -> None:
        if not self.token:
            self.login()

    def find_by_number(self, number: str) -> TransportLookupResult | None:
        lookup_number = str(number or "").strip()
        if not lookup_number or not self.has_credentials():
            return None

        for query in self._query_variants(lookup_number):
            payload = self._find_order(query, lookup_number)
            if payload:
                return self._build_result(lookup_number, payload)
        return None

    def _find_order(self, query: dict, lookup_number: str) -> dict | None:
        try:
            payload = self._post_order_query(query)
        except requests.RequestException:
            return None
        if not payload:
            return None

        order = self._select_order(payload, lookup_number)
        if not order:
            return None
        return self._enrich_order(order)

    def _post_order_query(self, query: dict) -> dict | None:
        self.ensure_authenticated()
        response = self.session.post(
            f"{self.api_v1_base_url}/orders/query",
            params={"page": 0, "size": 20, "sort": "createDate,desc"},
            json={**query, "orderType": query.get("orderType")},
            headers=self._headers(),
            timeout=self.timeout,
        )
        if response.status_code == 401:
            self.token = None
            self.ensure_authenticated()
            response = self.session.post(
                f"{self.api_v1_base_url}/orders/query",
                params={"page": 0, "size": 20, "sort": "createDate,desc"},
                json={**query, "orderType": query.get("orderType")},
                headers=self._headers(),
                timeout=self.timeout,
            )
        if response.status_code >= 400:
            return None
        payload = response.json()
        return payload if isinstance(payload, dict) else None

    def _enrich_order(self, order: dict) -> dict:
        order_id = order.get("orderId") or order.get("id")
        payload = {"order": order}
        if not order_id:
            return payload

        details = self._get_optional(f"{self.api_v1_base_url}/order/{order_id}")
        cargoes = self._get_optional(f"{self.api_v1_base_url}/order/{order_id}/cargoes")
        history = self._get_optional(f"{self.api_v1_base_url}/orders/{order_id}/history-statuses")
        if details:
            payload["details"] = details
        if cargoes:
            payload["cargoes"] = cargoes
        if history:
            payload["history"] = history
        return payload

    def _get_optional(self, url: str):
        try:
            self.ensure_authenticated()
            response = self.session.get(url, headers=self._headers(), timeout=self.timeout)
            if response.status_code == 401:
                self.token = None
                self.ensure_authenticated()
                response = self.session.get(url, headers=self._headers(), timeout=self.timeout)
            if response.status_code >= 400:
                return None
            return response.json()
        except (requests.RequestException, ValueError):
            return None

    def _build_result(self, lookup_number: str, payload: dict) -> TransportLookupResult:
        latest_status = self._latest_status(payload)
        status_code = self._status_code(latest_status) or self._status_code(payload.get("order", {}))
        details = payload.get("details", {}) if isinstance(payload.get("details"), dict) else {}
        order = payload.get("order", {}) if isinstance(payload.get("order"), dict) else {}
        status_label = (
            self._public_status_label(latest_status)
            or self._public_status_label(details)
            or self._public_status_label(order)
            or self._status_label(details)
            or self._status_label(order)
            or self._cargo_status_label(payload)
            or self._status_label(latest_status)
        )
        carrier_track_number = self._carrier_track_number(payload)
        tracking_url = self._tracking_url(payload, carrier_track_number or lookup_number)
        if tracking_url and not payload.get("trackingUrl") and not payload.get("tracking_url"):
            payload = {**payload, "trackingUrl": tracking_url}

        return TransportLookupResult(
            adapter=self.name,
            lookup_number=lookup_number,
            payload=payload,
            erp_order_number=self._erp_order_number(payload),
            carrier_track_number=carrier_track_number,
            delivery_status_code=status_code,
            delivery_status_label=status_label,
        )

    def _query_variants(self, number: str) -> list[dict]:
        variants = [
            {"senderOrderId": number},
            {"clientOrderId": number},
            {"omniBarcode": number},
            {"cargoBarcode": number},
            {"barcode": number},
        ]
        normalized = normalize_track_number(number)
        if normalized and normalized != number:
            variants.extend(
                [
                    {"senderOrderId": normalized},
                    {"clientOrderId": normalized},
                ]
            )
        return variants

    def _select_order(self, payload: dict, number: str) -> dict | None:
        content = payload.get("content")
        if not isinstance(content, list) or not content:
            return None

        exact_fields = ("senderOrderId", "clientOrderId", "omniBarcode", "cargoBarcode", "barcode")
        for order in content:
            if not isinstance(order, dict):
                continue
            if any(self._same_number(order.get(field), number) for field in exact_fields):
                return order
        return next((order for order in content if isinstance(order, dict)), None)

    @staticmethod
    def _same_number(left, right: str) -> bool:
        if left is None:
            return False
        left_raw = str(left).strip()
        right_raw = str(right).strip()
        if left_raw == right_raw:
            return True
        return normalize_track_number(left_raw) == normalize_track_number(right_raw)

    def _erp_order_number(self, payload: dict) -> str | None:
        order = payload.get("order") if isinstance(payload.get("order"), dict) else {}
        details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
        for source in (order, details):
            for key in ("senderOrderId", "clientOrderId", "sender_order_id", "client_order_id"):
                value = source.get(key)
                normalized = normalize_track_number(str(value or ""))
                if normalized:
                    return normalized
        return None

    def _carrier_track_number(self, payload: dict) -> str | None:
        order = payload.get("order") if isinstance(payload.get("order"), dict) else {}
        cargoes = payload.get("cargoes") if isinstance(payload.get("cargoes"), list) else []
        for source in [order, *[item for item in cargoes if isinstance(item, dict)]]:
            for key in ("omniBarcode", "cargoBarcode", "barcode", "barcodes"):
                value = source.get(key)
                if isinstance(value, list) and value:
                    return str(value[0]).strip()
                if value is not None and str(value).strip():
                    return str(value).strip()
        return None

    @staticmethod
    def _tracking_url(payload: dict, track_number: str | None) -> str | None:
        order = payload.get("order") if isinstance(payload.get("order"), dict) else {}
        details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
        for source in (payload, order, details):
            for key in ("trackingUrl", "tracking_url", "trackingLink", "tracking_link"):
                value = source.get(key)
                if value is not None and str(value).strip():
                    return str(value).strip()

        track = str(track_number or "").strip()
        if not track:
            return None
        return f"https://fivepost.ru/tracking/?id={quote(track, safe='')}"

    @staticmethod
    def _latest_status(payload: dict) -> dict:
        history = payload.get("history") if isinstance(payload.get("history"), list) else []
        return next((item for item in reversed(history) if isinstance(item, dict)), {})

    @staticmethod
    def _cargo_status_label(payload: dict) -> str | None:
        cargoes = payload.get("cargoes") if isinstance(payload.get("cargoes"), list) else []
        for cargo in cargoes:
            if not isinstance(cargo, dict):
                continue
            value = FivePostClient._status_label(cargo)
            if value:
                return value
        return None

    @staticmethod
    def _status_code(source: dict) -> str | None:
        for key in ("status", "executionStatus", "code", "key"):
            value = source.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    @staticmethod
    def _status_label(source: dict) -> str | None:
        if not isinstance(source, dict):
            return None
        cargo_status = FivePostClient._clean_status_part(source.get("cargoStatus") or source.get("cargo_status"))
        if cargo_status:
            return FivePostClient._with_location(cargo_status, source)

        for key in ("statusName", "executionStatusName", "value_i18n", "label", "name"):
            value = source.get(key)
            if value is not None and str(value).strip():
                return FivePostClient._with_location(str(value).strip(), source)
        return None

    @staticmethod
    def _public_status_label(source: dict) -> str | None:
        if not isinstance(source, dict):
            return None

        execution_status = FivePostClient._clean_status_part(
            source.get("executionStatus") or source.get("execution_status")
        )
        if not execution_status:
            return None

        status = execution_status.upper()
        location = FivePostClient._clean_status_part(
            source.get("locationName")
            or source.get("location_name")
            or source.get("statusLocationName")
            or source.get("status_location_name")
        )
        reason = FivePostClient._clean_status_part(
            source.get("statusChangeReasonDesc") or source.get("status_change_reason_desc")
        )
        reason = (reason or "").upper()

        if status in {"CREATED", "APPROVED"}:
            return "Ожидается передача заказа в 5post"

        if status in {
            "RECEIVED_IN_WAREHOUSE_IN_DETAILS",
            "SORTED_IN_WAREHOUSE",
            "PLACED_IN_CONSOLIDATION_CELL_IN_WAREHOUSE",
            "COMPLECTED_IN_WAREHOUSE",
            "READY_TO_BE_SHIPPED_FROM_WAREHOUSE",
        }:
            return f"Обрабатывается на складе {location}" if location else "Обрабатывается на складе"

        if status == "SHIPPED":
            if reason == "OTHER_MILE":
                return "Покинул склад. Ожидайте поступления в пункт выдачи"
            return f"Покинул склад {location}" if location else "Покинул склад"

        if status in {"RECEIVED_IN_STORE", "PLACED_IN_POSTAMAT"}:
            return "Доставлен в пункт выдачи"

        if status == "PICKED_UP":
            return "Вручен получателю"

        return None

    @staticmethod
    def _clean_status_part(value) -> str | None:
        if value is None:
            return None
        result = str(value).strip()
        return result or None

    @staticmethod
    def _with_location(label: str, source: dict) -> str:
        location = FivePostClient._clean_status_part(
            source.get("statusLocationName")
            or source.get("status_location_name")
            or source.get("locationName")
            or source.get("location_name")
        )
        if not location:
            return label
        if label.endswith((" с", " на", " в", " из", " до", " по")):
            return f"{label} {location}"
        return label

    def _headers(self, authorized: bool = True) -> dict:
        headers = {
            "Accept": "application/json",
            "Accept-Language": "ru-RU;q=0.5",
            "Content-Type": "application/json",
        }
        if authorized:
            self.ensure_authenticated()
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

from urllib.parse import quote

import requests

from order_status_service.config import SAFEROUTE_API_BASE_URL
from order_status_service.transport.adapters import TransportLookupResult
from order_status_service.utils import find_tracking_code, normalize_track_number


class SafeRouteClient:
    name = "saferoute"

    def __init__(
        self,
        base_url: str = SAFEROUTE_API_BASE_URL,
        public_base_url: str | None = None,
        email: str | None = None,
        password: str | None = None,
        timeout: int = 15,
    ):
        self.base_url = base_url.rstrip("/")
        self.public_base_url = (public_base_url or self._root_base_url(self.base_url)).rstrip("/")
        self.api_v2_base_url = self.base_url if self.base_url.endswith("/v2") else f"{self.base_url}/v2"
        self.email = str(email or "").strip()
        self.password = str(password or "").strip()
        self.timeout = timeout
        self.session = requests.Session()
        self.token = None

    @staticmethod
    def _root_base_url(base_url: str) -> str:
        return base_url[:-3].rstrip("/") if base_url.rstrip("/").endswith("/v2") else base_url.rstrip("/")

    def has_credentials(self) -> bool:
        return bool(self.email and self.password)

    def login(self) -> None:
        if not self.has_credentials():
            raise RuntimeError("SafeRoute credentials are not configured")

        response = self.session.post(
            f"{self.api_v2_base_url}/auth/login",
            json={"email": self.email, "password": self.password},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        nested_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        token = payload.get("token") or payload.get("access_token") or nested_data.get("token")
        if not token:
            raise RuntimeError("SafeRoute auth response does not contain token")
        self.token = str(token)

    def ensure_authenticated(self) -> None:
        if not self.token:
            self.login()

    def get_authorized_tracking_data(self, number: str) -> dict | None:
        if not self.has_credentials():
            return None

        tracking_number = str(number or "").strip()
        if not tracking_number:
            return None

        for field in ("id", "trackNumber", "cmsId"):
            try:
                payload = self._get_authorized_tracking_data(field, tracking_number)
            except requests.RequestException:
                payload = None
            if payload:
                return payload
        return None

    def get_authorized_order_search_data(self, number: str) -> dict | None:
        if not self.has_credentials():
            return None

        tracking_number = str(number or "").strip()
        if not tracking_number:
            return None

        try:
            payload = self._get_authorized_order_search_data(tracking_number)
        except requests.RequestException:
            return None
        return self._select_order_search_result(payload, tracking_number)

    def _get_authorized_tracking_data(self, field: str, number: str) -> dict | None:
        self.ensure_authenticated()
        response = self.session.get(
            f"{self.api_v2_base_url}/tracking",
            params={field: number},
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
            timeout=self.timeout,
        )
        if response.status_code == 401:
            self.token = None
            self.ensure_authenticated()
            response = self.session.get(
                f"{self.api_v2_base_url}/tracking",
                params={field: number},
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.token}",
                },
                timeout=self.timeout,
            )
        if response.status_code >= 400:
            return None
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("SafeRoute tracking response is not an object")
        return payload

    def _get_authorized_order_search_data(self, number: str):
        self.ensure_authenticated()
        response = self.session.get(
            f"{self.api_v2_base_url}/orders",
            params={"search": number, "page": 1, "perPage": 100},
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
            timeout=self.timeout,
        )
        if response.status_code == 401:
            self.token = None
            self.ensure_authenticated()
            response = self.session.get(
                f"{self.api_v2_base_url}/orders",
                params={"search": number, "page": 1, "perPage": 100},
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.token}",
                },
                timeout=self.timeout,
            )
        if response.status_code >= 400:
            return None
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, (dict, list)):
            raise RuntimeError("SafeRoute orders response is not an object or list")
        return payload

    def _select_order_search_result(self, payload, number: str) -> dict | None:
        candidates: list[dict] = []

        def collect(value) -> None:
            if isinstance(value, dict):
                if any(
                    key in value
                    for key in (
                        "trackNumber",
                        "track_number",
                        "cmsId",
                        "cms_id",
                        "trackingUrl",
                        "tracking_url",
                        "statusHistory",
                        "status_history",
                    )
                ):
                    candidates.append(value)
                    return
                for nested in value.values():
                    collect(nested)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        collect(payload)
        if not candidates:
            return None

        needle = str(number).strip()
        for candidate in candidates:
            for key in ("id", "trackNumber", "track_number", "cmsId", "cms_id", "orderNumber", "order_number"):
                value = candidate.get(key)
                if value is not None and str(value).strip() == needle:
                    return candidate

        normalized_needle = normalize_track_number(needle)
        if normalized_needle:
            for candidate in candidates:
                for key in ("cmsId", "cms_id", "orderNumber", "order_number", "trackNumber", "track_number"):
                    value = candidate.get(key)
                    if value is not None and normalize_track_number(str(value)) == normalized_needle:
                        return candidate

        return candidates[0]

    def get_tracking_data(self, number: str) -> dict | None:
        result = self.find_by_number(number)
        return result.payload if result else None

    def find_by_number(self, number: str) -> TransportLookupResult | None:
        lookup_number = str(number or "").strip()
        if not lookup_number:
            return None

        payload = self.get_authorized_order_search_data(lookup_number)
        if not payload:
            payload = self.get_authorized_tracking_data(lookup_number)
        if not payload and not self.has_credentials():
            payload = self.get_public_tracking_data(lookup_number)
        if not payload:
            return None

        erp_order_number = normalize_track_number(find_tracking_code(payload) or "")
        latest_status = self._latest_status(payload)
        return TransportLookupResult(
            adapter=self.name,
            lookup_number=lookup_number,
            payload=payload,
            erp_order_number=erp_order_number or None,
            carrier_track_number=self._carrier_track_number(payload),
            delivery_status_code=str(latest_status.get("code") or latest_status.get("statusCode") or "").strip() or None,
        )

    def get_public_tracking_data(self, number: str) -> dict | None:
        response = self.session.get(
            f"{self.public_base_url}/site/tracking/{quote(number, safe='')}",
            headers={"Accept": "application/json"},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            return None
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("SafeRoute tracking response is not an object")
        return payload

    def get_track_number(self, number: str) -> str | None:
        result = self.find_by_number(number)
        return result.erp_order_number if result else None

    @staticmethod
    def _carrier_track_number(payload: dict) -> str | None:
        value = payload.get("trackNumber") or payload.get("track_number")
        return str(value).strip() if value is not None and str(value).strip() else None

    @staticmethod
    def _latest_status(payload: dict) -> dict:
        history = payload.get("statusHistory") or payload.get("status_history") or []
        if not isinstance(history, list):
            return {}
        return next((item for item in history if isinstance(item, dict)), {})


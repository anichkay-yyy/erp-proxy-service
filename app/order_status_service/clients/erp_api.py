import requests

from order_status_service.exceptions import ProductionHistoryNotFound


class ErpApiClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        company_slug: str,
        computer_token: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.company_slug = company_slug
        self.computer_token = computer_token
        self.session = requests.Session()
        self.token = None

    def _headers(self, authenticated: bool = False) -> dict:
        headers = {"Accept": "application/json"}
        if authenticated:
            if not self.token:
                raise RuntimeError("ERP API token is missing")
            headers["Authorization"] = f"Bearer {self.token}"
            headers["X-Company-Slug"] = self.company_slug
        return headers

    def login(self) -> None:
        headers = self._headers()
        if self.computer_token:
            headers["X-COMPUTER-TOKEN"] = self.computer_token
        response = self.session.post(
            f"{self.base_url}/api/tokens",
            json={
                "email": self.email,
                "password": self.password,
                "remember": True,
            },
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("token")
        if not token:
            raise RuntimeError("ERP API token response does not contain token")
        self.token = token

    def ensure_authenticated(self) -> None:
        if not self.token:
            self.login()

    def get_order_production_history_items(self, order_id: int) -> list[dict]:
        self.ensure_authenticated()
        try:
            return self._get_order_production_history_items(order_id)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 401:
                self.token = None
                self.login()
                return self._get_order_production_history_items(order_id)
            raise

    def _get_order_production_history_items(self, order_id: int) -> list[dict]:
        response = self.session.get(
            f"{self.base_url}/api/orders/{order_id}/production-history-items",
            headers=self._headers(authenticated=True),
            timeout=30,
        )
        if response.status_code == 404:
            raise ProductionHistoryNotFound(f"Production history for order {order_id} was not found")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("ERP API production history response is not an array")
        return payload



from order_status_service.clients.erp_api import ErpApiClient
from order_status_service.clients.platform_admin import PlatformAdminClient
from order_status_service.config import BASE_URL, DEFAULT_COOKIE_JAR
from order_status_service.exceptions import OrderIdNotFound
from order_status_service.labels import history_status_map
from order_status_service.order_status import latest_platform_order_status
from order_status_service.transport.adapters import TransportAdapter
from order_status_service.utils import normalize_track_number


def summarize_delivery_fields(order: dict) -> dict:
    delivery_system = order.get("delivery_system") if isinstance(order.get("delivery_system"), dict) else {}
    delivery_data = order.get("delivery_data") if isinstance(order.get("delivery_data"), dict) else {}
    return {
        "delivery_system_id": order.get("delivery_system_id"),
        "delivery_system_type": delivery_system.get("type") or delivery_data.get("type"),
        "delivery_system_name": delivery_system.get("name") or delivery_data.get("name"),
        "tracking_number": order.get("tracking_number"),
        "delivery_shipment_id": delivery_data.get("shipment_id"),
        "delivery_shipment_tracking_link": order.get("delivery_shipment_tracking_link"),
        "platform_status_updated_at": order.get("status_updated_at"),
    }


class PlatformAdminService:
    def __init__(
        self,
        email: str,
        password: str,
        base_url: str = BASE_URL,
        locale: str = "en",
        company: str = "company-wavwh",
        cookie_jar_path: str = DEFAULT_COOKIE_JAR,
        default_by_date: str = "04/05/2024 - 05/20/2026",
        erp_api_client: ErpApiClient | None = None,
        transport_adapter: TransportAdapter | None = None,
    ):
        self.email = email
        self.password = password
        self.locale = locale
        self.company = company
        self.default_by_date = default_by_date
        self.client = PlatformAdminClient(base_url, cookie_jar_path)
        self.erp_api_client = erp_api_client
        self.transport_adapter = transport_adapter

    def ensure_authenticated(self) -> None:
        try:
            self.client.ensure_page_csrf(self.locale, self.company)
        except Exception:
            self.client.login(self.locale, self.email, self.password)
            self.client.ensure_page_csrf(self.locale, self.company)

    def get_orders(
        self,
        order_number: str | None = None,
        query: str | None = None,
        query_type: str = "number",
        by_date: str | None = None,
        start: int = 0,
        length: int = 25,
        raw: bool = False,
        filters: dict | None = None,
    ) -> dict | list[dict]:
        self.ensure_authenticated()
        request = {
            "locale": self.locale,
            "company": self.company,
            "by_date": by_date or self.default_by_date,
            "query": query if query is not None else (order_number or ""),
            "query_type": query_type,
            "start": start,
            "length": length,
            "filters": filters,
        }
        try:
            payload = self.client.get_orders(**request)
        except (RuntimeError, ValueError):
            self.client.login(self.locale, self.email, self.password)
            self.client.ensure_page_csrf(self.locale, self.company)
            payload = self.client.get_orders(**request)
        if raw:
            return payload
        return payload.get("data", [])

    def get_order_by_number(self, order_number: str, by_date: str | None = None) -> dict | None:
        for query_type in ("number", "track"):
            orders = self.get_orders(
                order_number=order_number,
                query_type=query_type,
                by_date=by_date,
                length=1,
            )
            if orders:
                return orders[0]
        return None

    def get_exact_order_by_number(self, order_number: str, by_date: str | None = None) -> dict:
        attempts = []
        for query_type in ("number", "track"):
            payload = self.get_orders(
                order_number=order_number,
                query_type=query_type,
                by_date=by_date,
                length=2,
                raw=True,
            )
            data = payload.get("data", [])
            records_filtered = payload.get("recordsFiltered")
            if records_filtered == 1 and len(data) == 1:
                return data[0]
            attempts.append(f"{query_type}: recordsFiltered={records_filtered}, count={len(data)}")
        raise OrderIdNotFound(
            f"Expected exactly one order for number/track {order_number}; " + "; ".join(attempts)
        )

    def get_order_id_by_number(self, order_number: str, by_date: str | None = None) -> int:
        order = self.get_exact_order_by_number(order_number, by_date=by_date)
        order_id = order.get("id")
        if order_id is None:
            raise OrderIdNotFound(f"Order id is missing for number {order_number}")
        return int(order_id)

    def resolve_order_id_by_number(
        self,
        order_number: str,
        by_date: str | None = None,
        transport_lookup_number: str | None = None,
    ) -> tuple[str, int]:
        normalized_order_number = normalize_track_number(order_number)
        if not normalized_order_number:
            raise OrderIdNotFound("Order number is empty")

        try:
            return normalized_order_number, self.get_order_id_by_number(normalized_order_number, by_date=by_date)
        except OrderIdNotFound as initial_error:
            if not self.transport_adapter:
                raise initial_error

            transport_order_number = self.find_transport_order_number(
                transport_lookup_number or order_number,
                normalized_order_number,
            )
            if not transport_order_number:
                raise initial_error

            fallback_order_number = normalize_track_number(transport_order_number)
            if not fallback_order_number:
                raise OrderIdNotFound("Transport lookup does not contain an ERP order number") from initial_error

            try:
                return fallback_order_number, self.get_order_id_by_number(fallback_order_number, by_date=by_date)
            except OrderIdNotFound as exc:
                raise OrderIdNotFound(
                    f"Order {normalized_order_number} was not found; "
                    f"transport order {fallback_order_number} was not found"
                ) from exc

    def resolve_order_by_number(
        self,
        order_number: str,
        by_date: str | None = None,
        transport_lookup_number: str | None = None,
    ) -> tuple[str, dict]:
        normalized_order_number = normalize_track_number(order_number)
        if not normalized_order_number:
            raise OrderIdNotFound("Order number is empty")

        try:
            return normalized_order_number, self.get_exact_order_by_number(normalized_order_number, by_date=by_date)
        except OrderIdNotFound as initial_error:
            if not self.transport_adapter:
                raise initial_error

            transport_order_number = self.find_transport_order_number(
                transport_lookup_number or order_number,
                normalized_order_number,
            )
            if not transport_order_number:
                raise initial_error

            fallback_order_number = normalize_track_number(transport_order_number)
            if not fallback_order_number:
                raise OrderIdNotFound("Transport lookup does not contain an ERP order number") from initial_error

            try:
                return fallback_order_number, self.get_exact_order_by_number(fallback_order_number, by_date=by_date)
            except OrderIdNotFound as exc:
                raise OrderIdNotFound(
                    f"Order {normalized_order_number} was not found; "
                    f"transport order {fallback_order_number} was not found"
                ) from exc

    def find_transport_order_number(self, *numbers: str | None) -> str | None:
        if not self.transport_adapter:
            return None

        seen: set[str] = set()
        for number in numbers:
            tracking_number = str(number or "").strip()
            if not tracking_number or tracking_number in seen:
                continue
            seen.add(tracking_number)
            result = self.transport_adapter.find_by_number(tracking_number)
            if result and result.erp_order_number:
                return result.erp_order_number
        return None

    def get_order_production_history_by_track_number(
        self,
        track_number: str,
        by_date: str | None = None,
    ) -> dict:
        order_number = normalize_track_number(track_number)
        if not order_number:
            raise OrderIdNotFound("Track number does not contain an order number")
        return self.get_order_production_history_by_order_number(
            order_number,
            by_date=by_date,
            transport_lookup_number=track_number,
        )

    def get_order_production_history_by_order_number(
        self,
        order_number: str,
        by_date: str | None = None,
        transport_lookup_number: str | None = None,
    ) -> dict:
        order_number = normalize_track_number(order_number)
        if not order_number:
            raise OrderIdNotFound("Order number is empty")
        resolved_order_number, platform_order = self.resolve_order_by_number(
            order_number,
            by_date=by_date,
            transport_lookup_number=transport_lookup_number,
        )
        latest_platform_status = latest_platform_order_status(platform_order)
        if not latest_platform_status:
            return {
                "status": None,
                "changed_at": None,
                "order_number": resolved_order_number,
                "platform_status": platform_order.get("status"),
                "payment_status": platform_order.get("payment_status"),
                **summarize_delivery_fields(platform_order),
            }
        return {
            **latest_platform_status,
            "order_number": resolved_order_number,
            "platform_status": platform_order.get("status"),
            "payment_status": platform_order.get("payment_status"),
            **summarize_delivery_fields(platform_order),
        }

    def get_history_status_map(self, locale: str = "ru") -> dict:
        return history_status_map(locale)

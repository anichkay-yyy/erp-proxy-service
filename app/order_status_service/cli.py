import argparse
import getpass
import json
import os
import sys

from order_status_service.clients.erp_api import ErpApiClient
from order_status_service.clients.platform_admin import PlatformAdminClient
from order_status_service.config import (
    BASE_URL,
    DEFAULT_BY_DATE,
    DEFAULT_COOKIE_JAR,
    DEFAULT_DOCUMENT_RETENTION_DAYS,
    DEFAULT_DOCUMENT_UPLOAD_MAX_BYTES,
    DEFAULT_ERP_API_COMPANY_SLUG,
    ERP_API_BASE_URL,
    FIVEPOST_API_BASE_URL,
    SAFEROUTE_API_BASE_URL,
    YANDEX_DELIVERY_API_BASE_URL,
)
from order_status_service.documents.store import DocumentStore
from order_status_service.exceptions import OrderIdNotFound, ProductionHistoryNotFound
from order_status_service.http_server import run_http_service
from order_status_service.service import PlatformAdminService
from order_status_service.transport.adapters import CompositeTransportAdapter, TransportAdapter
from order_status_service.transport.fivepost_client import FivePostClient
from order_status_service.transport.saferoute_client import SafeRouteClient
from order_status_service.transport.yandex_delivery_client import YandexDeliveryClient


def get_credentials(args) -> tuple[str, str]:
    email = args.email or os.environ.get("ERP_PROXY_EMAIL") or os.environ.get("PHOTO_PRINT_EMAIL")
    password = args.password or os.environ.get("ERP_PROXY_PASSWORD") or os.environ.get("PHOTO_PRINT_PASSWORD")
    if not email:
        if not sys.stdin.isatty():
            raise SystemExit("ERP_PROXY_EMAIL or PHOTO_PRINT_EMAIL is required")
        email = input("Email: ").strip()
    if not password:
        if not sys.stdin.isatty():
            raise SystemExit("ERP_PROXY_PASSWORD or PHOTO_PRINT_PASSWORD is required")
        password = getpass.getpass("Password: ")
    return email, password


def build_erp_api_client(args, email: str, password: str) -> ErpApiClient:
    erp_email = args.erp_api_email or os.environ.get("ERP_API_EMAIL") or email
    erp_password = args.erp_api_password or os.environ.get("ERP_API_PASSWORD") or password
    company_slug = args.erp_api_company_slug or os.environ.get("ERP_API_COMPANY_SLUG", DEFAULT_ERP_API_COMPANY_SLUG)
    computer_token = args.erp_api_computer_token or os.environ.get("ERP_API_COMPUTER_TOKEN")
    return ErpApiClient(
        base_url=args.erp_api_base_url,
        email=erp_email,
        password=erp_password,
        company_slug=company_slug,
        computer_token=computer_token,
    )


def build_transport_adapter(args) -> TransportAdapter:
    adapters: list[TransportAdapter] = [
        SafeRouteClient(
            base_url=args.saferoute_api_base_url,
            public_base_url=args.saferoute_public_api_base_url,
            email=args.saferoute_email,
            password=args.saferoute_password,
        )
    ]
    fivepost_client = FivePostClient(
        base_url=args.fivepost_api_base_url,
        login=args.fivepost_login,
        password=args.fivepost_password,
    )
    if fivepost_client.has_credentials():
        adapters.append(fivepost_client)
    yandex_delivery_client = YandexDeliveryClient(
        base_url=args.yandex_delivery_api_base_url,
        oauth_token=args.yandex_delivery_oauth_token,
    )
    if yandex_delivery_client.has_credentials():
        adapters.append(yandex_delivery_client)
    return CompositeTransportAdapter(adapters)


def build_document_store(args) -> DocumentStore:
    return DocumentStore(
        database_url=args.database_url,
        retention_days=args.document_retention_days,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Small client for platform-admin Laravel session auth")
    parser.add_argument(
        "command",
        choices=(
            "login",
            "csrf",
            "orders",
            "search-order",
            "get-order-id-by-number",
            "production-history",
            "serve",
        ),
    )
    parser.add_argument("--base-url", default=os.environ.get("ERP_PROXY_BASE_URL", BASE_URL))
    parser.add_argument("--erp-api-base-url", default=os.environ.get("ERP_API_BASE_URL", ERP_API_BASE_URL))
    parser.add_argument("--saferoute-api-base-url", default=os.environ.get("SAFEROUTE_API_BASE_URL", SAFEROUTE_API_BASE_URL))
    parser.add_argument("--saferoute-public-api-base-url", default=os.environ.get("SAFEROUTE_PUBLIC_API_BASE_URL"))
    parser.add_argument("--saferoute-email", default=os.environ.get("SAFEROUTE_EMAIL"))
    parser.add_argument("--saferoute-password", default=os.environ.get("SAFEROUTE_PASSWORD"))
    parser.add_argument("--fivepost-api-base-url", default=os.environ.get("FIVEPOST_API_BASE_URL", FIVEPOST_API_BASE_URL))
    parser.add_argument("--fivepost-login", default=os.environ.get("FIVEPOST_LOGIN"))
    parser.add_argument("--fivepost-password", default=os.environ.get("FIVEPOST_PASSWORD"))
    parser.add_argument(
        "--yandex-delivery-api-base-url",
        default=os.environ.get("YANDEX_DELIVERY_API_BASE_URL", YANDEX_DELIVERY_API_BASE_URL),
    )
    parser.add_argument(
        "--yandex-delivery-oauth-token",
        default=os.environ.get("YANDEX_DELIVERY_OAUTH_TOKEN") or os.environ.get("YANDEX_DELIVERY_TOKEN"),
    )
    parser.add_argument("--erp-api-email")
    parser.add_argument("--erp-api-password")
    parser.add_argument("--erp-api-company-slug")
    parser.add_argument("--erp-api-computer-token")
    parser.add_argument("--database-url", default=os.environ.get("ERP_PROXY_DATABASE_URL") or os.environ.get("DATABASE_URL"))
    parser.add_argument(
        "--document-retention-days",
        type=int,
        default=int(os.environ.get("DOCUMENT_RETENTION_DAYS", str(DEFAULT_DOCUMENT_RETENTION_DAYS))),
    )
    parser.add_argument(
        "--document-upload-max-bytes",
        type=int,
        default=int(os.environ.get("DOCUMENT_UPLOAD_MAX_BYTES", str(DEFAULT_DOCUMENT_UPLOAD_MAX_BYTES))),
    )
    parser.add_argument("--locale", default=os.environ.get("ERP_PROXY_LOCALE", "en"))
    parser.add_argument("--company", default=os.environ.get("ERP_PROXY_COMPANY", "company-wavwh"))
    parser.add_argument("--cookie-jar", default=os.environ.get("ERP_PROXY_COOKIE_JAR", DEFAULT_COOKIE_JAR))
    parser.add_argument("--email")
    parser.add_argument("--password")
    parser.add_argument("--order-number", default="365675")
    parser.add_argument("--query", default="")
    parser.add_argument("--query-type", default="number")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--length", type=int, default=25)
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--by-date", default=os.environ.get("ERP_PROXY_BY_DATE", DEFAULT_BY_DATE))
    parser.add_argument("--force-csrf", action="store_true")
    parser.add_argument("--host", default=os.environ.get("ERP_PROXY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("ERP_PROXY_PORT", "8000")))
    args = parser.parse_args()

    client = PlatformAdminClient(args.base_url, args.cookie_jar)

    if args.command == "login":
        email, password = get_credentials(args)
        client.login(args.locale, email, password)
        print(f"authenticated; cookies saved to {args.cookie_jar}")
        return 0

    if args.command == "csrf":
        client.ensure_page_csrf(args.locale, args.company)
        payload = client.refresh_csrf(force=args.force_csrf)
        print(payload)
        print(f"cookies saved to {args.cookie_jar}")
        return 0

    if args.command in ("orders", "search-order", "get-order-id-by-number", "production-history", "serve"):
        email, password = get_credentials(args)
        service = PlatformAdminService(
            email=email,
            password=password,
            base_url=args.base_url,
            locale=args.locale,
            company=args.company,
            cookie_jar_path=args.cookie_jar,
            default_by_date=args.by_date,
            erp_api_client=None,
            transport_adapter=build_transport_adapter(args),
        )
        if args.command == "serve":
            run_http_service(
                service,
                args.host,
                args.port,
                document_store=build_document_store(args),
                document_upload_max_bytes=args.document_upload_max_bytes,
            )
            return 0

        if args.command == "get-order-id-by-number":
            try:
                print(service.get_order_id_by_number(args.order_number, by_date=args.by_date))
                return 0
            except OrderIdNotFound:
                return 44

        if args.command == "production-history":
            try:
                payload = service.get_order_production_history_by_track_number(
                    args.order_number,
                    by_date=args.by_date,
                )
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 0
            except (OrderIdNotFound, ProductionHistoryNotFound):
                return 44

        payload = service.get_orders(
            order_number=args.order_number if args.command == "search-order" else None,
            query=args.query if args.command == "orders" else None,
            query_type=args.query_type,
            start=args.start,
            length=args.length,
            raw=True,
        )
        if args.raw:
            print(payload)
            return 0

        print(
            {
                "recordsTotal": payload.get("recordsTotal"),
                "recordsFiltered": payload.get("recordsFiltered"),
                "data": [summarize_order(row) for row in payload.get("data", [])],
            }
        )
        return 0

    return 1


def summarize_order(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "number": row.get("number"),
        "status": row.get("status"),
        "created_at": row.get("created_at"),
        "status_updated_at": row.get("status_updated_at"),
    }

#!/usr/bin/env python3
import os

from order_status_service.config import (
    BASE_URL,
    DEFAULT_BY_DATE,
    DEFAULT_COOKIE_JAR,
    DEFAULT_DOCUMENT_RETENTION_DAYS,
    DEFAULT_DOCUMENT_UPLOAD_MAX_BYTES,
    FIVEPOST_API_BASE_URL,
    SAFEROUTE_API_BASE_URL,
    YANDEX_DELIVERY_API_BASE_URL,
)
from order_status_service.documents.store import DocumentStore
from order_status_service.http_server import run_http_service
from order_status_service.service import PlatformAdminService
from order_status_service.transport.adapters import CompositeTransportAdapter
from order_status_service.transport.fivepost_client import FivePostClient
from order_status_service.transport.saferoute_client import SafeRouteClient
from order_status_service.transport.yandex_delivery_client import YandexDeliveryClient


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer") from exc


def required_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    raise SystemExit(f"{' or '.join(names)} is required")


def build_transport_adapter() -> CompositeTransportAdapter:
    adapters = [
        SafeRouteClient(
            base_url=os.environ.get("SAFEROUTE_API_BASE_URL", SAFEROUTE_API_BASE_URL),
            public_base_url=os.environ.get("SAFEROUTE_PUBLIC_API_BASE_URL"),
            email=os.environ.get("SAFEROUTE_EMAIL"),
            password=os.environ.get("SAFEROUTE_PASSWORD"),
        )
    ]

    fivepost_client = FivePostClient(
        base_url=os.environ.get("FIVEPOST_API_BASE_URL", FIVEPOST_API_BASE_URL),
        login=os.environ.get("FIVEPOST_LOGIN"),
        password=os.environ.get("FIVEPOST_PASSWORD"),
    )
    if fivepost_client.has_credentials():
        adapters.append(fivepost_client)

    yandex_delivery_client = YandexDeliveryClient(
        base_url=os.environ.get("YANDEX_DELIVERY_API_BASE_URL", YANDEX_DELIVERY_API_BASE_URL),
        oauth_token=os.environ.get("YANDEX_DELIVERY_OAUTH_TOKEN") or os.environ.get("YANDEX_DELIVERY_TOKEN"),
    )
    if yandex_delivery_client.has_credentials():
        adapters.append(yandex_delivery_client)

    return CompositeTransportAdapter(adapters)


def main() -> int:
    service = PlatformAdminService(
        email=required_env("ERP_PROXY_EMAIL", "PHOTO_PRINT_EMAIL"),
        password=required_env("ERP_PROXY_PASSWORD", "PHOTO_PRINT_PASSWORD"),
        base_url=os.environ.get("ERP_PROXY_BASE_URL", BASE_URL),
        locale=os.environ.get("ERP_PROXY_LOCALE", "en"),
        company=os.environ.get("ERP_PROXY_COMPANY", "company-wavwh"),
        cookie_jar_path=os.environ.get("ERP_PROXY_COOKIE_JAR", DEFAULT_COOKIE_JAR),
        default_by_date=os.environ.get("ERP_PROXY_BY_DATE", DEFAULT_BY_DATE),
        erp_api_client=None,
        transport_adapter=build_transport_adapter(),
    )

    document_store = DocumentStore(
        database_url=os.environ.get("ERP_PROXY_DATABASE_URL") or os.environ.get("DATABASE_URL"),
        retention_days=env_int("DOCUMENT_RETENTION_DAYS", DEFAULT_DOCUMENT_RETENTION_DAYS),
    )

    run_http_service(
        service=service,
        host=os.environ.get("ERP_PROXY_HOST", "127.0.0.1"),
        port=env_int("ERP_PROXY_PORT", 8000),
        document_store=document_store,
        document_upload_max_bytes=env_int("DOCUMENT_UPLOAD_MAX_BYTES", DEFAULT_DOCUMENT_UPLOAD_MAX_BYTES),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

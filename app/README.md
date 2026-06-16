# erp-proxy

Small HTTP proxy for platform-admin order lookup.

## Build

```bash
docker build -t erp-proxy .
```

## Run

```bash
docker run --rm -p 8000:8000 \
  -e ERP_PROXY_EMAIL='your-login@example.com' \
  -e ERP_PROXY_PASSWORD='your-password' \
  -v erp-proxy-cookies:/data \
  erp-proxy
```

## Endpoint

```bash
curl -i 'http://127.0.0.1:8000/getOrderIdByNumber?trackNumber=376831-7btxs'
```

This endpoint normalizes the input, finds the order in platform-admin, and reads
production state from platform-admin timestamp fields. It does not call
`https://erp.photo-print.co/api/orders/{order}/production-history-items`.
If platform-admin does not find the order, the proxy tries
`https://api.saferoute.ru/site/tracking/{number}` first. When SafeRoute returns
a tracking code, the proxy normalizes that code and retries platform-admin; if
that retry also fails, the endpoint returns `404`.
If the platform-admin `post_production_finished_at` field is present, it checks uploaded delivery documents:

- first the date when `post_production_finished` was assigned;
- then the next day when the date has records but this order is absent;
- returns `{"type":"tommorow","date":"YYYY-MM-DD"}` when the next-day document has not been uploaded yet.

The input value is normalized to an ERP order number before lookup:

- remove everything after `_`
- remove everything after `-`
- remove non-digits
- trim whitespace

Response:

- `200` with JSON containing `type`, `date`, `order_status`, and `payment_status`.
- `type=unpaid` when platform-admin finds the order and `payment_status=unpaid`.
- `type=new` when platform-admin finds a new paid order that has not entered production.
- `type=in_work` for paid orders that are already in production but do not have `post_production_finished_at` yet.
- `type=shipped` or `type=tommorow` after `post_production_finished_at`, depending on delivery documents.
- `404` when no orders are found or more than one order matches.
- `400` when input is missing or cannot be normalized.

Optional query params:

- `trackNumber`, `trackingNumber`, `track`, `tracking`, `number`, or `orderNumber`
- `byDate` / `by_date`, for example `01/01/2024 - 12/31/2030`

SafeRoute fallback env:

- `SAFEROUTE_API_BASE_URL`, defaults to `https://api.saferoute.ru`

Transport adapters:

- SafeRoute is always configured and can use public tracking without credentials.
- 5post is enabled when `FIVEPOST_LOGIN` and `FIVEPOST_PASSWORD` are set.
- Yandex Delivery is enabled when `YANDEX_DELIVERY_OAUTH_TOKEN` is set. For the
  current ERP channel `delivery_system_id=1407` / `delivery_system_type=yandex_to_point`
  it uses the Yandex Delivery across Russia API at
  `https://b2b-authproxy.taxi.yandex.net/api/b2b/platform/request/*`. The old
  `Яндекс Доставка Apiship` channel is intentionally not mapped to it.

Healthcheck:

```bash
curl 'http://127.0.0.1:8000/health'
```

## Documents

Small upload UI:

```bash
open 'http://127.0.0.1:8000/documents'
```

API:

```bash
curl -F 'document_date=2026-05-20' \
  -F 'document=@/path/to/document.pdf' \
  'http://127.0.0.1:8000/api/documents'

curl 'http://127.0.0.1:8000/api/documents'

curl -X DELETE 'http://127.0.0.1:8000/api/documents/<document-id>'
```

Documents are stored in Postgres for 3 days. PDF parser currently extracts only:

- `agent_order_number` from `№ заказа (в кодировке агента)`
- `delivery_address` from `Адрес доставки`

All other parsed columns are ignored.

Document env:

- `ERP_PROXY_DATABASE_URL` or `DATABASE_URL`, required for document endpoints
- `DOCUMENT_RETENTION_DAYS`, defaults to `3`
- `DOCUMENT_UPLOAD_MAX_BYTES`, defaults to `20971520`

## Database migrations

The document tables are managed by Alembic. The service runs `alembic upgrade head`
on startup when `ERP_PROXY_DATABASE_URL` or `DATABASE_URL` is configured.

Manual migration commands:

```bash
alembic -c alembic.ini upgrade head
alembic -c alembic.ini current
```

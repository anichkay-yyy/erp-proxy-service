FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ERP_PROXY_HOST=0.0.0.0 \
    ERP_PROXY_PORT=8000 \
    ERP_PROXY_COOKIE_JAR=/data/platform_admin_cookies.txt

WORKDIR /app

RUN apk add --no-cache --upgrade libcrypto3 libssl3

RUN addgroup -S app && adduser -S app -G app && mkdir -p /data && chown app:app /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY erp_proxy.py .
COPY alembic.ini .
COPY alembic ./alembic
COPY order_status_service ./order_status_service

USER app
EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.getenv('ERP_PROXY_PORT', '8000'), timeout=2).read()" || exit 1

CMD ["python", "erp_proxy.py"]

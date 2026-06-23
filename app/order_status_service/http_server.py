from __future__ import annotations

import json
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import parse_qs, urlparse

from order_status_service.config import DEFAULT_DOCUMENT_UPLOAD_MAX_BYTES
from order_status_service.widgets.documents import documents_app_html
from order_status_service.exceptions import DocumentDateNotFound, OrderIdNotFound, ProductionHistoryNotFound
from order_status_service.http_utils import parse_multipart_form
from order_status_service.status_response import build_main_endpoint_response
from order_status_service.transport.saferoute_delivery import build_saferoute_delivery_response
from order_status_service.utils import json_default, normalize_track_number, sanitize_filename


def widgets_catalog_json() -> str:
    """Read the built-in widgets catalog."""
    return files("order_status_service.widgets").joinpath("widgets.json").read_text(encoding="utf-8")


def run_http_service(
    service: PlatformAdminService,
    host: str,
    port: int,
    document_store: DocumentStore | None = None,
    document_upload_max_bytes: int = DEFAULT_DOCUMENT_UPLOAD_MAX_BYTES,
) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self.send_text(200, "ok\n")
                return

            if parsed.path == "/widgets/widgets.json":
                self.send_json_text(200, widgets_catalog_json())
                return

            if parsed.path in ("/widgets", "/widgets/"):
                self.send_redirect(308, "/widgets/widgets.json")
                return

            if parsed.path in ("/widgets/documents", "/widgets/documents/"):
                self.send_html(200, documents_app_html())
                return

            if parsed.path in ("/documents", "/documents/"):
                self.send_redirect(308, "/widgets/documents")
                return

            if parsed.path == "/api/documents":
                self.handle_list_documents(parsed.query)
                return

            if parsed.path == "/historyStatusMap":
                self.handle_history_status_map(parsed.query)
                return

            if parsed.path == "/getOrderIdByNumber":
                self.handle_get_order_production_history(parsed.query)
                return

            self.send_text(404, "not found\n")

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/documents":
                self.handle_upload_document()
                return

            self.send_text(404, "not found\n")

        def do_DELETE(self):
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/documents/"):
                document_id = parsed.path.rsplit("/", 1)[-1]
                self.handle_delete_document(document_id)
                return

            if parsed.path == "/api/documents":
                params = parse_qs(parsed.query)
                document_id = (params.get("id") or [""])[0]
                self.handle_delete_document(document_id)
                return

            self.send_text(404, "not found\n")

        def handle_list_documents(self, query: str):
            if not document_store or not document_store.enabled:
                self.send_json(503, {"error": "Postgres is not configured"})
                return

            params = parse_qs(query)
            raw_limit = (params.get("limit") or ["50"])[0]
            try:
                limit = max(1, min(200, int(raw_limit)))
            except ValueError:
                limit = 50

            try:
                documents = document_store.list_documents(limit=limit)
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
                return

            self.send_json(
                200,
                {
                    "retention_days": document_store.retention_days,
                    "documents": documents,
                },
            )

        def handle_upload_document(self):
            if not document_store or not document_store.enabled:
                self.send_json(503, {"error": "Postgres is not configured"})
                return

            content_length = self.headers.get("Content-Length")
            try:
                length = int(content_length or "0")
            except ValueError:
                self.send_json(400, {"error": "Invalid Content-Length"})
                return
            if length <= 0:
                self.send_json(400, {"error": "Empty request body"})
                return
            if length > document_upload_max_bytes:
                self.send_json(413, {"error": "Document is too large"})
                return

            content_type = self.headers.get("Content-Type", "")
            body = self.rfile.read(length)
            try:
                fields, files = parse_multipart_form(body, content_type)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
                return

            document_date_raw = fields.get("document_date") or fields.get("date") or ""
            try:
                document_date = date.fromisoformat(document_date_raw)
            except ValueError:
                self.send_json(400, {"error": "document_date must be YYYY-MM-DD"})
                return

            uploaded_file = files.get("document") or files.get("file")
            if not uploaded_file:
                self.send_json(400, {"error": "document file is required"})
                return

            filename = uploaded_file.get("filename") or "document"
            file_content_type = uploaded_file.get("content_type")
            raw_bytes = uploaded_file.get("content") or b""
            if not raw_bytes:
                self.send_json(400, {"error": "document file is empty"})
                return

            try:
                document = document_store.create_document(
                    document_date=document_date,
                    original_filename=sanitize_filename(filename),
                    content_type=file_content_type,
                    raw_bytes=raw_bytes,
                )
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
                return

            self.send_json(201, {"document": document})

        def handle_delete_document(self, document_id: str):
            if not document_store or not document_store.enabled:
                self.send_json(503, {"error": "Postgres is not configured"})
                return
            if not document_id:
                self.send_json(400, {"error": "document id is required"})
                return

            try:
                deleted = document_store.delete_document(document_id)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
                return
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
                return
            if not deleted:
                self.send_json(404, {"error": "document was not found"})
                return

            self.send_json(200, {"deleted": True, "id": document_id})

        def handle_history_status_map(self, query: str):
            params = parse_qs(query)
            locale = (params.get("locale") or params.get("lang") or ["ru"])[0]
            self.send_json(200, service.get_history_status_map(locale))

        def handle_get_order_production_history(self, query: str):
            params = parse_qs(query)
            raw_track_number = (
                params.get("trackNumber")
                or params.get("trackingNumber")
                or params.get("track")
                or params.get("tracking")
                or params.get("number")
                or params.get("orderNumber")
                or [""]
            )[0]
            by_date = (params.get("by_date") or params.get("byDate") or [None])[0]
            if not normalize_track_number(raw_track_number):
                self.send_json(
                    400,
                    {
                        "found": False,
                        "error": "track number does not contain an order number",
                    },
                )
                return

            try:
                payload = build_main_endpoint_response(
                    service=service,
                    document_store=document_store,
                    raw_track_number=raw_track_number,
                    by_date=by_date,
                )
            except (OrderIdNotFound, ProductionHistoryNotFound):
                fallback_payload = build_saferoute_delivery_response(
                    service.transport_adapter,
                    raw_track_number,
                )
                if fallback_payload:
                    self.send_json(200, fallback_payload)
                    return
                self.send_json(404, {"found": False})
                return
            except DocumentDateNotFound:
                self.send_json(404, {"found": False})
                return
            except Exception as exc:
                self.send_json(500, {"found": False, "error": str(exc)})
                return

            self.send_json(200, payload)

        def log_message(self, format, *args):
            return

        def send_text(self, status: int, body: str):
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def send_html(self, status: int, body: str):
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def send_redirect(self, status: int, location: str):
            self.send_response(status)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def send_json_text(self, status: int, body: str):
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def send_json(self, status: int, body: dict):
            encoded = json.dumps(body, ensure_ascii=False, default=json_default).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"serving http://{host}:{port}/getOrderIdByNumber?trackNumber=376831-7btxs")
    print(f"serving http://{host}:{port}/widgets/widgets.json")
    print(f"serving http://{host}:{port}/widgets/documents")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

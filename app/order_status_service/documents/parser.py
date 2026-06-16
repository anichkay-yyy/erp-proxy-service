import re
from io import BytesIO

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

from order_status_service.utils import normalize_track_number


def parse_document_delivery_records(
    raw_bytes: bytes,
    original_filename: str,
    content_type: str | None,
) -> list[dict]:
    filename = original_filename.lower()
    is_pdf = filename.endswith(".pdf") or (content_type or "").lower().startswith("application/pdf")
    if not is_pdf:
        raise ValueError("Only PDF documents are supported")
    text = extract_pdf_text(raw_bytes)
    return parse_5post_delivery_records_from_text(text)


def extract_pdf_text(raw_bytes: bytes) -> str:
    if not PdfReader:
        raise RuntimeError("pypdf is not installed")
    reader = PdfReader(BytesIO(raw_bytes))
    pages = []
    for page in reader.pages:
        try:
            page_text = page.extract_text(extraction_mode="layout") or ""
        except TypeError:
            page_text = page.extract_text() or ""
        pages.append(page_text)
    return "\n".join(pages)


def parse_5post_delivery_records_from_text(text: str) -> list[dict]:
    records: list[dict] = []
    for line in text.splitlines():
        clean = line.replace("\x0c", "").strip()
        if not re.match(r"^\d{1,4}\s+", clean):
            continue

        columns = [part.strip() for part in re.split(r"\s{2,}", clean) if part.strip()]
        if len(columns) < 8:
            continue

        agent_order_number = normalize_track_number(columns[1])
        delivery_address = columns[4]
        if not agent_order_number or not delivery_address:
            continue
        if not re.search(r"[А-Яа-яA-Za-z]", delivery_address):
            continue

        records.append(
            {
                "agent_order_number": agent_order_number,
                "delivery_address": delivery_address,
            }
        )
    return records


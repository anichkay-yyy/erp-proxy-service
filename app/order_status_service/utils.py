import re
import uuid
from datetime import date, datetime, timedelta, timezone


def normalize_track_number(track_number: str) -> str:
    normalized = str(track_number or "").strip()
    if "_" in normalized:
        normalized = normalized.split("_", 1)[0]
    if "-" in normalized:
        normalized = normalized.split("-", 1)[0]
    leading_order_number = re.match(r"^\s*(\d{5,12})(?=\D|$)", normalized)
    if leading_order_number:
        return leading_order_number.group(1)
    normalized = re.sub(r"\D+", "", normalized)
    return normalized.strip()


def find_tracking_code(payload) -> str | None:
    if isinstance(payload, dict):
        for key in (
            "cmsId",
            "cms_id",
            "cmsID",
            "orderNumber",
            "order_number",
            "orderNo",
            "order_no",
            "trackNumber",
            "track_number",
            "trackingNumber",
            "tracking_number",
        ):
            value = payload.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
        for value in payload.values():
            nested = find_tracking_code(value)
            if nested:
                return nested
    if isinstance(payload, list):
        for item in payload:
            nested = find_tracking_code(item)
            if nested:
                return nested
    return None



def business_today() -> date:
    return datetime.now(timezone(timedelta(hours=3))).date()


def date_from_iso_datetime(value: str | None) -> date | None:
    if not value:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        try:
            return date.fromisoformat(normalized[:10])
        except ValueError:
            return None


def sanitize_filename(filename: str) -> str:
    cleaned = filename.replace("\\", "/").split("/")[-1].strip()
    return cleaned or "document"


def json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

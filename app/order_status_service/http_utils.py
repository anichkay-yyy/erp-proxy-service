import re


def parse_multipart_form(body: bytes, content_type: str) -> tuple[dict[str, str], dict[str, dict]]:
    match = re.search(r'boundary="?([^";]+)"?', content_type)
    if not match:
        raise ValueError("Content-Type boundary is missing")

    boundary = match.group(1).encode("utf-8")
    delimiter = b"--" + boundary
    fields: dict[str, str] = {}
    files: dict[str, dict] = {}

    for raw_part in body.split(delimiter):
        part = raw_part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        if part.endswith(b"--"):
            part = part[:-2].rstrip(b"\r\n")

        header_blob, separator, content = part.partition(b"\r\n\r\n")
        if not separator:
            continue

        headers = parse_part_headers(header_blob)
        disposition = headers.get("content-disposition", "")
        disposition_params = parse_header_params(disposition)
        name = disposition_params.get("name")
        if not name:
            continue

        if content.endswith(b"\r\n"):
            content = content[:-2]

        filename = disposition_params.get("filename")
        if filename is not None:
            files[name] = {
                "filename": filename,
                "content_type": headers.get("content-type"),
                "content": content,
            }
        else:
            fields[name] = content.decode("utf-8", errors="replace").strip()

    return fields, files


def parse_part_headers(header_blob: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    for raw_line in header_blob.decode("utf-8", errors="replace").split("\r\n"):
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def parse_header_params(value: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for chunk in value.split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        key, raw_value = chunk.split("=", 1)
        raw_value = raw_value.strip()
        if len(raw_value) >= 2 and raw_value[0] == '"' and raw_value[-1] == '"':
            raw_value = raw_value[1:-1]
        params[key.strip().lower()] = raw_value
    return params


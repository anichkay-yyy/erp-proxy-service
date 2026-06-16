import json
import uuid
from datetime import date

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

from order_status_service.config import DEFAULT_DOCUMENT_RETENTION_DAYS
from order_status_service.documents.parser import parse_document_delivery_records
from order_status_service.utils import normalize_track_number


class DocumentStore:
    def __init__(self, database_url: str | None, retention_days: int = DEFAULT_DOCUMENT_RETENTION_DAYS):
        self.database_url = database_url
        self.retention_days = retention_days

    @property
    def enabled(self) -> bool:
        return bool(self.database_url and psycopg)

    def _connect(self):
        if not self.database_url:
            raise RuntimeError("Postgres database URL is not configured")
        if not psycopg:
            raise RuntimeError("psycopg is not installed")
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def cleanup_expired(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM document_uploads WHERE expires_at <= now()")
            conn.execute("DELETE FROM document_records WHERE expires_at <= now()")

    def create_document(
        self,
        document_date: date,
        original_filename: str,
        content_type: str | None,
        raw_bytes: bytes,
    ) -> dict:
        self.cleanup_expired()
        parsed_records = parse_document_delivery_records(raw_bytes, original_filename, content_type)
        parse_status = "parsed" if parsed_records else "empty"
        document_id = str(uuid.uuid4())
        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    INSERT INTO document_uploads (
                        id,
                        document_date,
                        original_filename,
                        content_type,
                        size_bytes,
                        raw_bytes,
                        parse_status,
                        expires_at
                    )
                    VALUES (
                        %(id)s,
                        %(document_date)s,
                        %(original_filename)s,
                        %(content_type)s,
                        %(size_bytes)s,
                        %(raw_bytes)s,
                        %(parse_status)s,
                        now() + (%(retention_days)s::text || ' days')::interval
                    )
                    RETURNING
                        id,
                        document_date,
                        original_filename,
                        content_type,
                        size_bytes,
                        status,
                        parse_status,
                        created_at,
                        expires_at
                    """,
                    {
                        "id": document_id,
                        "document_date": document_date,
                        "original_filename": original_filename,
                        "content_type": content_type,
                        "size_bytes": len(raw_bytes),
                        "raw_bytes": raw_bytes,
                        "parse_status": parse_status,
                        "retention_days": self.retention_days,
                    },
                ).fetchone()
                for record in parsed_records:
                    conn.execute(
                        """
                        INSERT INTO document_records (
                            id,
                            document_id,
                            record_type,
                            agent_order_number,
                            delivery_address,
                            payload,
                            expires_at
                        )
                        VALUES (
                            %(id)s,
                            %(document_id)s,
                            'delivery_address',
                            %(agent_order_number)s,
                            %(delivery_address)s,
                            %(payload)s::jsonb,
                            now() + (%(retention_days)s::text || ' days')::interval
                        )
                        """,
                        {
                            "id": str(uuid.uuid4()),
                            "document_id": document_id,
                            "agent_order_number": record["agent_order_number"],
                            "delivery_address": record["delivery_address"],
                            "payload": json.dumps(record, ensure_ascii=False),
                            "retention_days": self.retention_days,
                        },
                    )
        result = dict(row)
        result["records_count"] = len(parsed_records)
        return result

    def list_documents(self, limit: int = 50) -> list[dict]:
        self.cleanup_expired()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    u.id,
                    u.document_date,
                    u.original_filename,
                    u.content_type,
                    u.size_bytes,
                    u.status,
                    u.parse_status,
                    u.created_at,
                    u.expires_at,
                    count(r.id)::int AS records_count
                FROM document_uploads u
                LEFT JOIN document_records r ON r.document_id = u.id
                GROUP BY u.id
                ORDER BY u.created_at DESC
                LIMIT %(limit)s
                """,
                {"limit": limit},
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_document(self, document_id: str) -> bool:
        try:
            normalized_document_id = str(uuid.UUID(str(document_id)))
        except ValueError as exc:
            raise ValueError("document id must be UUID") from exc

        with self._connect() as conn:
            row = conn.execute(
                """
                DELETE FROM document_uploads
                WHERE id = %(id)s
                RETURNING id
                """,
                {"id": normalized_document_id},
            ).fetchone()
        return row is not None

    def has_delivery_records_for_date(self, document_date: date) -> bool:
        self.cleanup_expired()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM document_uploads u
                    JOIN document_records r ON r.document_id = u.id
                    WHERE u.document_date = %(document_date)s
                      AND r.record_type = 'delivery_address'
                ) AS exists
                """,
                {"document_date": document_date},
            ).fetchone()
        return bool(row and row["exists"])

    def find_delivery_record(self, document_date: date, agent_order_number: str) -> dict | None:
        self.cleanup_expired()
        normalized_order_number = normalize_track_number(agent_order_number)
        if not normalized_order_number:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    r.agent_order_number,
                    r.delivery_address,
                    u.document_date
                FROM document_uploads u
                JOIN document_records r ON r.document_id = u.id
                WHERE u.document_date = %(document_date)s
                  AND r.record_type = 'delivery_address'
                  AND (
                    r.agent_order_number = %(agent_order_number)s
                    OR (
                      length(%(agent_order_number)s) >= 6
                      AND r.agent_order_number LIKE %(agent_order_prefix)s
                    )
                  )
                ORDER BY
                  CASE WHEN r.agent_order_number = %(agent_order_number)s THEN 0 ELSE 1 END,
                  length(r.agent_order_number) ASC,
                  r.created_at DESC
                LIMIT 1
                """,
                {
                    "document_date": document_date,
                    "agent_order_number": normalized_order_number,
                    "agent_order_prefix": f"{normalized_order_number}%",
                },
            ).fetchone()
        return dict(row) if row else None


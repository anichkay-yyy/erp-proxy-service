"""create document upload tables

Revision ID: 20260616_0001
Revises:
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op

revision = "20260616_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_uploads (
            id UUID PRIMARY KEY,
            document_date DATE NOT NULL,
            original_filename TEXT NOT NULL,
            content_type TEXT,
            size_bytes INTEGER NOT NULL,
            raw_bytes BYTEA NOT NULL,
            status TEXT NOT NULL DEFAULT 'uploaded',
            parse_status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_records (
            id UUID PRIMARY KEY,
            document_id UUID NOT NULL REFERENCES document_uploads(id) ON DELETE CASCADE,
            record_type TEXT NOT NULL,
            agent_order_number TEXT,
            delivery_address TEXT,
            payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute("ALTER TABLE document_records ADD COLUMN IF NOT EXISTS agent_order_number TEXT")
    op.execute("ALTER TABLE document_records ADD COLUMN IF NOT EXISTS delivery_address TEXT")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_uploads_expires_at
        ON document_uploads (expires_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_records_document_id
        ON document_records (document_id)
        """
    )


def downgrade() -> None:
    op.drop_index("idx_document_records_document_id", table_name="document_records")
    op.drop_index("idx_document_uploads_expires_at", table_name="document_uploads")
    op.drop_table("document_records")
    op.drop_table("document_uploads")

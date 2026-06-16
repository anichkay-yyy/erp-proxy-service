from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def run_database_migrations(database_url: str | None) -> None:
    if not database_url:
        return

    app_dir = Path(__file__).resolve().parents[1]
    config = Config(str(app_dir / "alembic.ini"))
    config.set_main_option("script_location", str(app_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", _sqlalchemy_database_url(database_url))
    command.upgrade(config, "head")


def _sqlalchemy_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url

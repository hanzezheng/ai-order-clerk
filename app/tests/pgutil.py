from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


def default_test_database_url() -> str:
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get(
        "DATABASE_URL",
        "postgresql://ubuntu@/ai_clerk_test?host=/var/run/postgresql",
    )


def postgres_url_or_skip() -> str:
    pytest.importorskip("psycopg")
    pytest.importorskip("sqlalchemy")
    url = default_test_database_url()
    try:
        from app.database.postgres.factory import create_postgres_engine

        engine = create_postgres_engine(url)
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        engine.dispose()
    except SQLAlchemyError as exc:
        pytest.skip(f"PostgreSQL 不可用: {exc}")
    except OSError as exc:
        pytest.skip(f"PostgreSQL 不可用: {exc}")
    return url


def alembic_ini() -> Path:
    return Path(__file__).resolve().parents[2] / "alembic.ini"

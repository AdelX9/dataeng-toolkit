"""Database connection helpers using SQLAlchemy 2.0."""

from __future__ import annotations
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine, Connection


def get_engine(url: str, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine with connection pooling and pre-ping."""
    return create_engine(url, pool_size=5, max_overflow=10, pool_pre_ping=True, echo=echo)


@contextmanager
def connect(engine: Engine) -> Generator[Connection, None, None]:
    """Context manager: auto-commit on success, rollback on error, always close."""
    conn = engine.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def test_connection(engine: Engine) -> dict:
    """Verify connectivity and return server info."""
    with connect(engine) as conn:
        row = conn.execute(text(
            "SELECT version() AS v, current_database() AS db, "
            "current_user AS u, now() AS t"
        )).mappings().one()
        return dict(row)


def get_tables(engine: Engine, schema: str = "public") -> list[str]:
    """List all table names in a schema."""
    return inspect(engine).get_table_names(schema=schema)

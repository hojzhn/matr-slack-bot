"""Postgres (Supabase) connection pool.

Reads the connection string from the ``DATABASE_URL`` env var. The pool is
created lazily on first use so the rest of the app imports cleanly even when no
database is configured — callers should gate on :func:`is_configured` first.

Connection string (Supabase → Project Settings → Database → Connection string):

    postgresql://postgres.<ref>:<password>@<host>.pooler.supabase.com:6543/postgres

Port 6543 is the transaction pooler — fine for the polling alert system and for
short CRUD queries. (LISTEN/NOTIFY would need the 5432 session pooler, but we
poll, so 6543 is the right default.)
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager

log = logging.getLogger(__name__)

_pool = None


def database_url() -> str | None:
    return os.environ.get("DATABASE_URL")


def is_configured() -> bool:
    return bool(database_url())


def _configure(conn):
    # Autocommit: each statement commits on its own. The poller's reads and the
    # single-row cursor/insert writes don't need multi-statement transactions.
    conn.autocommit = True


def get_pool():
    """Return the process-wide connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        from psycopg_pool import ConnectionPool  # imported lazily; optional dep

        url = database_url()
        if not url:
            raise RuntimeError("DATABASE_URL is not set")
        _pool = ConnectionPool(
            url,
            min_size=1,
            max_size=5,
            configure=_configure,
            open=True,
            # Don't block app startup forever if Supabase is unreachable.
            timeout=10,
        )
    return _pool


@contextmanager
def connection():
    """Borrow a connection from the pool for the duration of the ``with`` block."""
    with get_pool().connection() as conn:
        yield conn


def healthcheck() -> bool:
    """Run ``SELECT 1``; raises if the database is unreachable."""
    with connection() as conn:
        conn.execute("select 1")
    return True


def close():
    """Close the pool (e.g. on shutdown). Safe to call when never opened."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None

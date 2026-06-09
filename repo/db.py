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

    conn.autocommit = True


def get_pool():

    global _pool
    if _pool is None:
        from psycopg_pool import ConnectionPool

        url = database_url()
        if not url:
            raise RuntimeError("DATABASE_URL is not set")
        _pool = ConnectionPool(
            url,
            min_size=1,
            max_size=5,
            configure=_configure,
            open=True,

            timeout=10,
        )
    return _pool


@contextmanager
def connection():

    with get_pool().connection() as conn:
        yield conn


def healthcheck() -> bool:

    with connection() as conn:
        conn.execute("select 1")
    return True


def close():

    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None

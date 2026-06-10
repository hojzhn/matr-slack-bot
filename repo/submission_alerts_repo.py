from __future__ import annotations

import logging

from repo import db

log = logging.getLogger(__name__)


_PENDING_SQL = """
    select
        s.id          as submission_id,
        s.title       as title,
        s.name        as name,
        s.email       as email,
        s.description as description,
        s.size        as size,
        s.medium      as medium,
        s.image_kind  as image_kind,
        s.image_url   as image_url,
        s.image_name  as image_name,
        s.created_at  as created_at
    from submissions s
    where s.slack_notified is distinct from true
    order by s.created_at nulls last
"""


def fetch_pending_submissions() -> list[dict]:

    with db.connection() as conn:
        cur = conn.execute(_PENDING_SQL)
        rows = cur.fetchall()
        names = [d.name for d in cur.description]
    return [dict(zip(names, r)) for r in rows]


def mark_submissions_notified(submission_ids) -> None:

    submission_ids = [str(x) for x in submission_ids]
    if not submission_ids:
        return
    with db.connection() as conn:
        conn.execute(
            "update submissions set slack_notified = true where id = any(%s::uuid[])",
            (submission_ids,),
        )

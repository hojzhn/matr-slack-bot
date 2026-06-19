from __future__ import annotations

import logging

from repo import db

log = logging.getLogger(__name__)


_PENDING_SQL = """
    select
        j.id           as job_id,
        o.order_number as order_number,
        o.source       as source,
        o.purpose      as purpose,
        o.size         as size,
        o.orientation  as orientation,
        (
            select oi.url from order_images oi
            where oi.order_id = j.order_id
            order by oi.id
            limit 1
        )              as order_image_url,
        'started'::text         as event,
        j.printing_activated_at as changed_at
    from job_tracking j
    join orders o on o.id = j.order_id
    where j.printing_activated_at is not null
      and j.printing_started_slack_notified is distinct from true
    union all
    select
        j.id,
        o.order_number,
        o.source,
        o.purpose,
        o.size,
        o.orientation,
        (
            select oi.url from order_images oi
            where oi.order_id = j.order_id
            order by oi.id
            limit 1
        ),
        'completed'::text,
        j.printing_completed_at
    from job_tracking j
    join orders o on o.id = j.order_id
    where j.printing_completed_at is not null
      and j.printing_completed_slack_notified is distinct from true
    order by changed_at nulls last
"""


def fetch_pending_printing() -> list[dict]:

    with db.connection() as conn:
        cur = conn.execute(_PENDING_SQL)
        rows = cur.fetchall()
        names = [d.name for d in cur.description]
    return [dict(zip(names, r)) for r in rows]


def mark_printing_notified(pairs) -> None:

    started = [jid for jid, ev in pairs if ev == "started"]
    completed = [jid for jid, ev in pairs if ev == "completed"]
    if not started and not completed:
        return
    with db.connection() as conn:
        if started:
            conn.execute(
                "update job_tracking set printing_started_slack_notified = true where id = any(%s)",
                (started,),
            )
        if completed:
            conn.execute(
                "update job_tracking set printing_completed_slack_notified = true where id = any(%s)",
                (completed,),
            )

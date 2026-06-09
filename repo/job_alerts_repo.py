from __future__ import annotations

import logging

from repo import db

log = logging.getLogger(__name__)


_PENDING_SQL = """
    select
        j.id                as job_id,
        j.order_id          as order_id,
        j.direct_request_id as direct_request_id,
        o.order_number      as order_number,
        o.size              as size,
        o.orientation       as orientation,
        (
            select oi.url from order_images oi
            where oi.order_id = j.order_id
            order by oi.id
            limit 1
        )                   as order_image_url,
        d.request_name      as request_name,
        d.width             as width,
        d.height            as height,
        d.medium            as medium,
        d.method            as method,
        d.customer_name     as customer_name,
        d.url               as direct_url,
        coalesce(j.created_at, j.updated_at) as created_at
    from job_tracking j
    left join orders          o on o.id = j.order_id
    left join direct_requests d on d.id = j.direct_request_id
    where j.slack_notified is distinct from true
    order by coalesce(j.created_at, j.updated_at) nulls last
"""


def fetch_pending_jobs() -> list[dict]:

    with db.connection() as conn:
        cur = conn.execute(_PENDING_SQL)
        rows = cur.fetchall()
        names = [d.name for d in cur.description]
    return [dict(zip(names, r)) for r in rows]


def mark_jobs_notified(job_ids) -> None:

    job_ids = list(job_ids)
    if not job_ids:
        return
    with db.connection() as conn:
        conn.execute(
            "update job_tracking set slack_notified = true where id = any(%s)",
            (job_ids,),
        )

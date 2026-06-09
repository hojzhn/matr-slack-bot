
from __future__ import annotations

import logging

from repo import db

log = logging.getLogger(__name__)


# Every order_proofs row that hasn't been alerted yet, joined to its order for the
# order number / size / orientation. The image_url lives on order_proofs itself.
# `slack_notified IS DISTINCT FROM TRUE` treats both false and NULL as pending.
# `changed_at` prefers the customer response time, falling back to row timestamps.
_PENDING_SQL = """
    select
        p.id                as proof_id,
        o.order_number      as order_number,
        o.size              as size,
        o.orientation       as orientation,
        p.customer_response as customer_response,
        p.customer_notes    as customer_notes,
        coalesce(p.response_at, p.updated_at, p.created_at) as changed_at,
        p.image_url         as image_url
    from order_proofs p
    join orders o on o.id = p.order_id
    where p.slack_notified is distinct from true
    order by coalesce(p.response_at, p.updated_at, p.created_at) nulls last
"""


def fetch_pending() -> list[dict]:
    """Return unalerted order_proofs rows (joined to their order), oldest first."""
    with db.connection() as conn:
        cur = conn.execute(_PENDING_SQL)
        rows = cur.fetchall()
        names = [d.name for d in cur.description]
    return [dict(zip(names, r)) for r in rows]


def mark_notified(proof_ids) -> None:
    """Set slack_notified = true for the given order_proofs ids (so no re-alert).

    This UPDATE deliberately changes only slack_notified, so the re-arm trigger
    (`order_proofs_reset_notified`) leaves it alone and we don't loop.
    """
    proof_ids = list(proof_ids)
    if not proof_ids:
        return
    with db.connection() as conn:
        conn.execute(
            "update order_proofs set slack_notified = true where id = any(%s)",
            (proof_ids,),
        )


def insert_project(
    *,
    name: str,
    assignee: str | None = None,
    type: str | None = None,
    width_in: float | None = None,
    height_in: float | None = None,
    created_by: str | None = None,
    slack_item_id: str | None = None,
    status: str | None = None,
) -> int:

    with db.connection() as conn:
        row = conn.execute(
            """
            insert into projects
                (name, assignee, type, width_in, height_in, created_by, slack_item_id, status)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            returning id
            """,
            (name, assignee, type, width_in, height_in, created_by, slack_item_id, status),
        ).fetchone()
    return row[0]

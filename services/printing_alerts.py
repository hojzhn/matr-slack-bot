from __future__ import annotations

from services.order_alerts import _cap, _format_ts, fallback_text  # noqa: F401
from utils.images import thumbnail_url

_EVENT_LABEL = {"started": "Printing started", "completed": "Printing complete"}


def describe_printing(row: dict) -> dict:
    order_number = row.get("order_number") or "?"
    label = _EVENT_LABEL.get(row.get("event"), "Printing update")
    size_line = " / ".join(_cap(x) for x in (row.get("size"), row.get("orientation")) if x) or None
    return {
        "headline": f"[{order_number}] {label}",
        "body_lines": [size_line] if size_line else [],
        "when": _format_ts(row.get("changed_at")),
        "thumbnail_url": thumbnail_url(row.get("order_image_url")) or None,
        "thumbnail_alt": f"Order {order_number}",
    }

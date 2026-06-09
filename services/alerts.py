"""Alert formatting — pure logic.

Turns an ``order_proofs`` row (joined to its order) into the display fields for a
Slack alert. No Slack, no IO — trivially unit-testable. ``ui/`` renders it.
"""

from __future__ import annotations

# customer_response → headline verb. Unknown values fall back to "Image <Value>".
_RESULT_LABELS = {
    "approved": "Image Approved",
    "rejected": "Image Rejected",
    "pending": "Image Pending",
}


def describe_proof(row: dict) -> dict:
    """Return the display fields for one proof-change alert."""
    order_number = row.get("order_number") or "?"
    response = (row.get("customer_response") or "").strip()
    headline = _RESULT_LABELS.get(response.lower()) or (
        f"Image {response.title()}" if response else "Proof Updated"
    )

    size_line = " / ".join(x for x in (row.get("size"), row.get("orientation")) if x) or None
    note = (row.get("customer_notes") or "").strip() or None
    image_url = row.get("image_url")

    return {
        "headline": f"[{order_number}] {headline}",
        "size_line": size_line,
        "when": _format_ts(row.get("changed_at")),
        "note": note,
        "image_url": image_url,
        "filename": _filename(image_url),
    }


def _format_ts(ts) -> str | None:
    """ISO 8601 with millisecond precision (e.g. 2026-05-28T18:31:14.086+00:00)."""
    if ts is None:
        return None
    iso = getattr(ts, "isoformat", None)
    if iso:
        try:
            return ts.isoformat(timespec="milliseconds")
        except TypeError:  # not a datetime (e.g. a date)
            return ts.isoformat()
    return str(ts)


def _filename(url) -> str | None:
    """Last path segment of the image URL, query string stripped."""
    if not url:
        return None
    path = url.split("?", 1)[0].rstrip("/")
    return path.rsplit("/", 1)[-1] or None


def fallback_text(desc: dict) -> str:
    return desc["headline"]

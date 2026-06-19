from __future__ import annotations

from utils.images import thumbnail_url


_RESULT_LABELS = {
    "approved": "Image Approved",
    "rejected": "Image Rejected",
    "pending": "Image Pending",
}


def describe_proof(row: dict) -> dict:

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
        "image_url": thumbnail_url(image_url, width=600),
        "filename": _filename(image_url),
    }


def _format_ts(ts) -> str | None:

    if ts is None:
        return None
    iso = getattr(ts, "isoformat", None)
    if iso:
        try:
            return ts.isoformat(timespec="milliseconds")
        except TypeError:
            return ts.isoformat()
    return str(ts)


def _filename(url) -> str | None:

    if not url:
        return None
    path = url.split("?", 1)[0].rstrip("/")
    return path.rsplit("/", 1)[-1] or None


def fallback_text(desc: dict) -> str:
    return desc["headline"]

from __future__ import annotations


def describe_submission(row: dict) -> dict:

    title = (row.get("title") or "").strip()
    name = (row.get("name") or "").strip()
    label = title or name or "?"

    detail_lines = []

    who = name
    email = (row.get("email") or "").strip()
    if email:
        who = f"{who} <{email}>" if who else email
    if who:
        detail_lines.append(who)

    size_line = " / ".join(
        x.strip() for x in (row.get("size"), row.get("medium")) if (x or "").strip()
    ) or None
    if size_line:
        detail_lines.append(size_line)

    description = (row.get("description") or "").strip() or None

    image_url = row.get("image_url")
    image_name = (row.get("image_name") or "").strip() or _filename(image_url)

    return {
        "headline": f"[{label}] New Quote Request!",
        "detail_lines": detail_lines,
        "description": description,
        "when": _format_ts(row.get("created_at")),
        "image_url": image_url,
        "image_name": image_name,
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

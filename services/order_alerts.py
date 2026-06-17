from __future__ import annotations


def describe_job(row: dict) -> dict:

    if row.get("direct_request_id") is not None:
        return _describe_direct(row)
    return _describe_shopify(row)


def _describe_shopify(row: dict) -> dict:
    order_number = row.get("order_number") or "?"
    noun = "Shopify Order" if _is_shopify(row.get("source")) else "Job Row"
    qualifier = _purpose_qualifier(row.get("purpose"))
    label = f"{qualifier} {noun}" if qualifier else noun
    size_line = " / ".join(_cap(x) for x in (row.get("size"), row.get("orientation")) if x) or None
    return {
        "headline": f"[{order_number}] New {label}!",
        "body_lines": [size_line] if size_line else [],
        "when": _format_ts(row.get("created_at")),
        "thumbnail_url": row.get("order_image_url") or None,
        "thumbnail_alt": f"Order {order_number}",
    }


def _is_shopify(source) -> bool:

    return str(source or "").strip().lower() == "shopify"


def _purpose_qualifier(purpose) -> str | None:

    val = str(purpose or "").strip()
    if not val or val.lower() == "paid":
        return None
    return _cap(val)


def _describe_direct(row: dict) -> dict:
    request_name = row.get("request_name") or "?"
    body_lines = []
    dims = _dims(row.get("width"), row.get("height"), row.get("medium"))
    if dims:
        body_lines.append(dims)
    for key in ("method", "customer_name", "direct_url"):
        val = (row.get(key) or "").strip()
        if val:
            body_lines.append(val)
    return {
        "headline": f"[{request_name}] New Direct Request!",
        "body_lines": body_lines,
        "when": _format_ts(row.get("created_at")),
    }


def _dims(width, height, medium) -> str | None:

    size = None
    if width is not None and height is not None:
        size = f"{_num(width)} x {_num(height)}"
    parts = [p for p in (size, (medium or "").strip() or None) if p]
    return ", ".join(parts) or None


def _cap(s) -> str:

    s = str(s)
    return s[:1].upper() + s[1:]


def _num(x) -> str:

    try:
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    return str(int(f)) if f.is_integer() else str(f)


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


def fallback_text(desc: dict) -> str:
    return desc["headline"]

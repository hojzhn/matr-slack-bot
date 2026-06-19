from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

DEFAULT_WIDTH = 160


def thumbnail_url(url: str | None, width: int = DEFAULT_WIDTH) -> str | None:
    """Return a smaller variant of an image URL, for Slack thumbnails.

    Recognises Shopify CDN and Supabase storage URLs and asks each for a
    resized version; any other URL is returned unchanged. Best-effort — never
    raises, so a weird URL just falls through untouched.
    """
    if not url:
        return url
    try:
        parts = urlparse(url)
    except Exception:
        return url
    host = (parts.netloc or "").lower()

    # Supabase storage: public object endpoint -> image render endpoint.
    if "/storage/v1/object/public/" in parts.path:
        new_path = parts.path.replace(
            "/storage/v1/object/public/", "/storage/v1/render/image/public/", 1
        )
        return _with_query(parts._replace(path=new_path), width=width, quality=80)

    # Shopify CDN honours width/height query params.
    if "cdn.shopify.com" in host or host.endswith("myshopify.com"):
        return _with_query(parts, width=width)

    return url


def _with_query(parts, **extra) -> str:
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    for k, v in extra.items():
        q[str(k)] = str(v)
    return urlunparse(parts._replace(query=urlencode(q)))

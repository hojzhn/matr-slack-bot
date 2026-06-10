from __future__ import annotations


def build_job_alert_message(desc: dict) -> list[dict]:
    lines = [f"*{desc['headline']}*"]
    lines.extend(desc.get("body_lines") or [])
    if desc.get("when"):
        lines.append("")
        lines.append(desc["when"])

    section = {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}
    thumb = desc.get("thumbnail_url")
    if thumb:
        section["accessory"] = {
            "type": "image",
            "image_url": thumb,
            "alt_text": desc.get("thumbnail_alt") or "order image",
        }
    return [section]

from __future__ import annotations


def build_submission_alert_message(desc: dict) -> list[dict]:
    lines = [f"*{desc['headline']}*"]
    lines.extend(desc.get("detail_lines") or [])
    if desc.get("when"):
        lines.append(desc["when"])
    if desc.get("description"):
        lines.append(f"Description: {desc['description']}")

    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}]

    url = desc.get("image_url")
    if url:

        image = {"type": "image", "image_url": url, "alt_text": desc.get("image_name") or "submission"}
        if desc.get("image_name"):
            image["title"] = {"type": "plain_text", "text": desc["image_name"][:2000]}
        blocks.append(image)

    return blocks

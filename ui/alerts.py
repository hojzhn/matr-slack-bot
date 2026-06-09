from __future__ import annotations


def build_alert_message(desc: dict) -> list[dict]:
    lines = [f"*{desc['headline']}*"]
    if desc.get("size_line"):
        lines.append(desc["size_line"])
    if desc.get("when"):
        lines.append(desc["when"])
    if desc.get("note"):
        lines.append(f"Note: {desc['note']}")

    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}]

    url = desc.get("image_url")
    if url:

        image = {"type": "image", "image_url": url, "alt_text": desc.get("filename") or "proof"}
        if desc.get("filename"):
            image["title"] = {"type": "plain_text", "text": desc["filename"][:2000]}
        blocks.append(image)

    return blocks

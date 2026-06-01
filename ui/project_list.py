
import json

from ui.components import size_select_block

CALLBACK_ID = "project_create"

DETAILS_ACTION = "project_details_link"

SIZE_PRESET_BLOCK = "size_preset"
SIZE_PRESET_ACTION = "project_size_select"


def _is_file_input(col):
    return col.get("input") == "file" or col["type"] == "attachment"


def _with_placeholder(element, text):
    if text:
        element["placeholder"] = {"type": "plain_text", "text": text[:150]}
    return element


def _input_element(col):
    ctype = col["type"]
    placeholder = col.get("placeholder")

    if col.get("input") == "richtext":
        return _with_placeholder({"type": "rich_text_input", "action_id": "value"}, placeholder)
    if _is_file_input(col):
        # file_input doesn't support a placeholder.
        element = {"type": "file_input", "action_id": "value", "max_files": col.get("max_files", 1)}
        if col.get("filetypes"):
            element["filetypes"] = col["filetypes"]
        return element
    if ctype in ("date", "todo_due_date"):
        return _with_placeholder({"type": "datepicker", "action_id": "value"}, placeholder)
    if ctype in ("user", "todo_assignee"):
        return _with_placeholder({"type": "users_select", "action_id": "value"}, placeholder)
    if ctype == "rating":
        # Star rating, 1–5 (Slack's default scale).
        return _with_placeholder(
            {
                "type": "static_select",
                "action_id": "value",
                "options": [
                    {"text": {"type": "plain_text", "text": str(n)}, "value": str(n)}
                    for n in range(1, 6)
                ],
            },
            placeholder,
        )
    if ctype == "select":
        return _with_placeholder(
            {
                "type": "static_select",
                "action_id": "value",
                "options": [
                    {"text": {"type": "plain_text", "text": o["label"][:75]}, "value": o["value"]}
                    for o in col["options"]
                ],
            },
            placeholder,
        )
    if ctype == "checkbox":
        return {
            "type": "checkboxes",
            "action_id": "value",
            "options": [{"text": {"type": "plain_text", "text": "Yes"}, "value": "true"}],
        }
    # text / number / email / phone / link -> free text
    return _with_placeholder({"type": "plain_text_input", "action_id": "value"}, placeholder)


def _col_meta(col):

    meta = {"id": col["id"], "type": col["type"]}
    if _is_file_input(col):
        meta["input"] = "file"
    elif col.get("input"):
        meta["input"] = col["input"]  # e.g. "richtext"
    return meta


def build_create_modal(
    columns, list_id, title="New Project", hidden_defaults=None, extra_meta=None, lead_blocks=None
):

    blocks = list(lead_blocks or [])
    blocks += [
        {
            "type": "input",
            "block_id": col["id"],
            "optional": not col.get("required", col.get("is_primary", False)),
            "label": {"type": "plain_text", "text": (col.get("label") or col["name"])[:150]},
            "element": _input_element(col),
        }
        for col in columns
    ]

    meta = {"list_id": list_id, "cols": [_col_meta(c) for c in columns]}
    if hidden_defaults:
        meta["hidden"] = hidden_defaults
    if extra_meta:
        meta.update(extra_meta)

    return {
        "type": "modal",
        "callback_id": CALLBACK_ID,
        "private_metadata": json.dumps(meta),
        "title": {"type": "plain_text", "text": title[:24]},
        "submit": {"type": "plain_text", "text": "Create"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }


def _thumbnail_accessory(thumb, placeholder_url):
    """Image accessory for the card: the uploaded image, else a placeholder."""
    if thumb and thumb.get("id"):
        return {"type": "image", "slack_file": {"id": thumb["id"]}, "alt_text": "attachment"}
    if placeholder_url:
        return {"type": "image", "image_url": placeholder_url, "alt_text": "no file attached"}
    return None


def build_notification(name, assignee, creator, thumb, placeholder_url, item_url=None):

    lines = [f"*{name or 'Untitled'}*"]
    if assignee:
        lines.append(f"Assigned to <@{assignee}>")
    if creator:
        lines.append(f"Added by <@{creator}>")
    section = {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}
    accessory = _thumbnail_accessory(thumb, placeholder_url)
    if accessory:
        section["accessory"] = accessory
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "New item created"}},
        section,
    ]
    if item_url:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Details"},
                        "url": item_url,
                        "action_id": DETAILS_ACTION,
                    }
                ],
            }
        )
    return blocks


def build_info_modal(title, message):
    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": title[:24]},
        "close": {"type": "plain_text", "text": "Done"},
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": message}}],
    }


def build_size_preset_block(size_presets):
    return size_select_block(
        size_presets,
        "",
        block_id=SIZE_PRESET_BLOCK,
        action_id=SIZE_PRESET_ACTION,
        label="Size preset (fills Width / Height)",
        optional=True,
    )


def api_error_message(err, needed=None):
    if err == "missing_scope":
        return (
            f"The bot is missing the *{needed or 'required'}* scope. Add it under "
            "*OAuth & Permissions → Bot Token Scopes*, then reinstall the app."
        )
    if err in ("not_visible", "file_not_found", "list_not_found", "no_permission"):
        return (
            "The bot can't access this List. Open the List in Slack → *Share*, "
            "and give the bot (or a channel it's in) access — then try again."
        )
    return f"Slack API error:\n`{err}`"


SIZE_INCOMPLETE_MESSAGE = "Pick a size, or enter Width and Height below"

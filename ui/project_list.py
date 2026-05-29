"""Dumb view builders for ``/newproject`` — data in, Block Kit out.

No Slack client, no config, no schema fetching. The cog parses the list schema,
decides which columns are visible vs. hidden-with-defaults, and passes plain
column dicts in; these functions only render. A column dict may carry: ``label``
(display override), ``required``, ``placeholder``, and ``input``/``filetypes``/
``max_files`` (for a file-upload field).
"""

import json

CALLBACK_ID = "project_create"


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
    """The per-column info stashed in private_metadata for the submit handler."""
    meta = {"id": col["id"], "type": col["type"]}
    if _is_file_input(col):
        meta["input"] = "file"
    elif col.get("input"):
        meta["input"] = col["input"]  # e.g. "richtext"
    return meta


def build_create_modal(
    columns, list_id, title="New Project", hidden_defaults=None, extra_meta=None, lead_blocks=None
):
    """Render the create modal for the given (visible) ``columns``.

    ``lead_blocks`` are extra blocks rendered before the column inputs (e.g. the
    shared size-preset selector). ``hidden_defaults`` are ``{id, type, value}``
    for columns kept out of the modal but written on submit; ``extra_meta`` is
    merged into private_metadata (e.g. which column is the name/assignee, for the
    notification). Everything is stashed in private_metadata so the submit handler
    needs no schema re-fetch.
    """
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


def build_info_modal(title, message):
    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": title[:24]},
        "close": {"type": "plain_text", "text": "Done"},
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": message}}],
    }

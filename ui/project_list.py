"""Dumb view builders for ``/newproject`` — data in, Block Kit out.

No Slack client, no config, no schema fetching. The cog parses the list schema,
decides which columns are visible vs. hidden-with-defaults, and passes plain
column dicts in; these functions only render.
"""

import json

CALLBACK_ID = "project_create"


def _input_element(col):
    ctype = col["type"]
    if ctype == "date":
        return {"type": "datepicker", "action_id": "value"}
    if ctype == "user":
        return {"type": "users_select", "action_id": "value"}
    if ctype == "select":
        return {
            "type": "static_select",
            "action_id": "value",
            "options": [
                {"text": {"type": "plain_text", "text": o["label"][:75]}, "value": o["value"]}
                for o in col["options"]
            ],
        }
    if ctype == "checkbox":
        return {
            "type": "checkboxes",
            "action_id": "value",
            "options": [{"text": {"type": "plain_text", "text": "Yes"}, "value": "true"}],
        }
    # text / number / email / phone -> free text
    return {"type": "plain_text_input", "action_id": "value"}


def build_create_modal(columns, list_id, title="New Project", hidden_defaults=None):
    """Render the create modal for the given (visible) ``columns``.

    ``hidden_defaults`` is a list of ``{id, type, value}`` for columns kept out of
    the modal but still written on submit — stashed in private_metadata so the
    submit handler can append them without re-fetching the schema.
    """
    blocks = [
        {
            "type": "input",
            "block_id": col["id"],
            "optional": not col["is_primary"],
            "label": {"type": "plain_text", "text": col["name"][:150]},
            "element": _input_element(col),
        }
        for col in columns
    ]

    meta = {"list_id": list_id, "cols": [{"id": c["id"], "type": c["type"]} for c in columns]}
    if hidden_defaults:
        meta["hidden"] = hidden_defaults

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

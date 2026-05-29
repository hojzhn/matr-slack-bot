"""Project-list cog — ``/newproject`` creates an item in a Slack List.

Flow:
1. ``/newproject`` reads the target list's schema (``files.info`` →
   ``list_metadata``) and builds a modal with one input per editable column.
2. On submit, the typed values are turned into the ``initial_fields`` payload
   that ``slackLists.items.create`` expects (per-column-type value shapes), and
   a new row is created in the list.

The list id / slash command live in ``config.json`` (``project_list``), so the
modal adapts to whatever columns the list has — no field list is hard-coded.

Scopes (beyond the calculator's ``commands``-only footprint — see CLAUDE.md):
``files:read`` (``files.info`` reads the List schema), ``lists:read`` and
``lists:write`` (create items). Reinstall the app after adding them.
"""

import json
import logging

from slack_sdk.errors import SlackApiError

from ui.project_list import CALLBACK_ID, build_create_modal, build_info_modal
from utils.config import load_config

log = logging.getLogger(__name__)

# Column types we can render as a modal input. Everything else (created_by,
# last_edited_*, formulas, attachments, …) is read-only/auto and is skipped.
RENDERABLE_TYPES = {"text", "number", "date", "select", "email", "phone", "user", "checkbox"}


# --- schema parsing (pure) -------------------------------------------------

def parse_columns(file_obj):
    """Extract a normalized column list from a List file object.

    Returns dicts ``{id, name, type, options}`` where ``options`` is a list of
    ``{value, label}`` for select columns. Defensive about key names since the
    raw schema shape varies.
    """
    meta = (file_obj or {}).get("list_metadata") or {}
    schema = meta.get("schema") or []
    columns = []
    for col in schema:
        cid = col.get("id") or col.get("key")
        ctype = col.get("type")
        if not cid or not ctype:
            continue
        options = []
        raw_opts = (col.get("options") or {}).get("choices") or []
        for choice in raw_opts:
            value = choice.get("value") or choice.get("id")
            if value is None:
                continue
            options.append({"value": value, "label": choice.get("label") or value})
        columns.append(
            {
                "id": cid,
                "name": col.get("name") or col.get("key") or cid,
                "type": ctype,
                "options": options,
                "is_primary": bool(col.get("is_primary_column")),
            }
        )
    return columns


def renderable_columns(columns):
    return [c for c in columns if c["type"] in RENDERABLE_TYPES and (c["type"] != "select" or c["options"])]


# --- hidden columns / config defaults --------------------------------------

def _norm(name):
    """Normalize a column name for lenient matching (lowercase, no spaces)."""
    return "".join((name or "").lower().split())


def _is_hidden(col, project_list):
    """True if a column is excluded from the modal (matched by name or id)."""
    hidden = project_list.hidden_columns
    return col["id"] in hidden or _norm(col["name"]) in {_norm(h) for h in hidden}


def _configured_default(col, project_list):
    """Return the configured default value for a column, or None."""
    defaults = project_list.column_defaults
    if col["id"] in defaults:
        return defaults[col["id"]]
    by_name = {_norm(k): v for k, v in defaults.items()}
    return by_name.get(_norm(col["name"]))


def split_columns(columns, project_list):
    """Partition parsed columns into (visible_inputs, hidden_default_fields).

    Visible = renderable and not hidden. Hidden-default = hidden columns that
    have a configured default value (written automatically on submit). Hidden
    columns without a default are simply omitted (the List's own column default
    applies).
    """
    visible = [c for c in renderable_columns(columns) if not _is_hidden(c, project_list)]
    hidden_defaults = []
    for col in columns:
        if not _is_hidden(col, project_list):
            continue
        value = _configured_default(col, project_list)
        if value is not None:
            hidden_defaults.append({"id": col["id"], "type": col["type"], "value": value})
    return visible, hidden_defaults


def _api_error_message(exc):
    """A human-friendly message for a Slack API error (esp. scope/access issues)."""
    err = exc.response.get("error")
    if err == "missing_scope":
        needed = exc.response.get("needed", "the required scope")
        return (
            f"The bot is missing the *{needed}* scope. Add it under "
            "*OAuth & Permissions → Bot Token Scopes*, then reinstall the app."
        )
    if err in ("not_visible", "file_not_found", "list_not_found", "no_permission"):
        return (
            "The bot can't access this List. Open the List in Slack → *Share*, "
            "and give the bot (or a channel it's in) access — then try again."
        )
    return f"Slack API error:\n`{err or exc}`"


# --- value extraction → initial_fields (pure, testable) --------------------

def _rich_text(value):
    """Wrap a plain string in the Block Kit rich_text shape a text column wants."""
    return [
        {
            "type": "rich_text",
            "elements": [
                {"type": "rich_text_section", "elements": [{"type": "text", "text": value}]}
            ],
        }
    ]


def _read_input(block_state, ctype):
    """Pull the raw value for one column out of its block state, or None if empty."""
    el = block_state.get("value", {})
    if ctype == "date":
        return el.get("selected_date") or None
    if ctype == "user":
        return el.get("selected_user") or None
    if ctype == "select":
        opt = el.get("selected_option")
        return opt.get("value") if opt else None
    if ctype == "checkbox":
        return bool(el.get("selected_options"))
    text = el.get("value")
    return text.strip() if isinstance(text, str) and text.strip() else None


def _field_for(col_id, ctype, value):
    if ctype == "text":
        return {"column_id": col_id, "rich_text": _rich_text(value)}
    if ctype == "number":
        return {"column_id": col_id, "number": [float(value)]}
    if ctype == "date":
        return {"column_id": col_id, "date": [value]}
    if ctype == "select":
        return {"column_id": col_id, "select": [value]}
    if ctype == "user":
        return {"column_id": col_id, "user": [value]}
    if ctype == "email":
        return {"column_id": col_id, "email": [value]}
    if ctype == "phone":
        return {"column_id": col_id, "phone": [value]}
    if ctype == "checkbox":
        return {"column_id": col_id, "checkbox": bool(value)}
    raise ValueError(f"unsupported column type: {ctype!r}")


def extract_fields(state_values, cols):
    """Build the ``initial_fields`` list from modal state.

    ``cols`` is the ``[{id, type}, …]`` stashed in the modal's private_metadata.
    Returns ``(initial_fields, errors)``; ``errors`` maps block_id -> message.
    """
    fields = []
    errors = {}
    for col in cols:
        cid, ctype = col["id"], col["type"]
        block_state = state_values.get(cid, {})
        value = _read_input(block_state, ctype)

        if ctype == "checkbox":
            fields.append(_field_for(cid, ctype, value))
            continue
        if value is None:
            continue  # optional & blank (Slack enforces required inputs itself)
        if ctype == "number":
            try:
                value = float(value)
            except (TypeError, ValueError):
                errors[cid] = "Enter a number"
                continue
        fields.append(_field_for(cid, ctype, value))

    return fields, errors


# --- registration ----------------------------------------------------------

def register(app):
    pl = load_config().project_list
    if not pl:
        return  # feature not configured; nothing to register

    @app.command(pl.command)
    def open_new_project(ack, body, client):
        ack()
        trigger_id = body["trigger_id"]
        try:
            file_obj = client.files_info(file=pl.list_id)["file"]
        except SlackApiError as exc:
            log.exception("files.info failed for list %s", pl.list_id)
            client.views_open(
                trigger_id=trigger_id, view=build_info_modal("Error", _api_error_message(exc))
            )
            return
        except Exception as exc:  # network / unexpected
            log.exception("files.info failed for list %s", pl.list_id)
            client.views_open(
                trigger_id=trigger_id,
                view=build_info_modal("Error", f"Couldn't load the list:\n`{exc}`"),
            )
            return

        # Log the raw schema once so column parsing can be tuned if a type is off.
        log.info("list %s metadata: %s", pl.list_id, json.dumps(file_obj.get("list_metadata", {}))[:3000])

        visible, hidden_defaults = split_columns(parse_columns(file_obj), pl)
        if not visible:
            client.views_open(
                trigger_id=trigger_id,
                view=build_info_modal("Error", "No editable columns found in this list."),
            )
            return

        client.views_open(
            trigger_id=trigger_id,
            view=build_create_modal(visible, pl.list_id, pl.title, hidden_defaults),
        )

    @app.view(CALLBACK_ID)
    def submit_new_project(ack, view, client):
        meta = json.loads(view["private_metadata"])
        fields, errors = extract_fields(view["state"]["values"], meta["cols"])
        if errors:
            ack(response_action="errors", errors=errors)
            return

        # Append the configured defaults for columns kept out of the modal.
        for hidden in meta.get("hidden", []):
            try:
                fields.append(_field_for(hidden["id"], hidden["type"], hidden["value"]))
            except (ValueError, TypeError):
                log.warning("skipping invalid default for column %s", hidden["id"])

        try:
            client.slackLists_items_create(list_id=meta["list_id"], initial_fields=fields)
        except SlackApiError as exc:
            log.exception("slackLists.items.create failed")
            reason = exc.response.get("error") or "unknown_error"
            ack(response_action="errors", errors={meta["cols"][0]["id"]: f"Create failed: {reason}"})
            return
        except Exception as exc:
            log.exception("slackLists.items.create failed")
            ack(response_action="errors", errors={meta["cols"][0]["id"]: f"Create failed: {exc}"})
            return

        ack(
            response_action="update",
            view=build_info_modal("Created ✅", "Your project was added to the list."),
        )

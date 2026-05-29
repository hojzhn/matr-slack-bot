"""Project-list cog — ``/newproject`` creates an item in a Slack List.

Flow:
1. ``/newproject`` reads the target list's schema (``files.info`` →
   ``list_metadata``) and builds a modal from the configured ``fields`` (an
   ordered allow-list with per-field label/required overrides). With no fields
   configured it auto-renders every editable column.
2. On submit, the typed values are turned into the ``initial_fields`` payload
   that ``slackLists.items.create`` expects (per-column-type value shapes),
   defaults are added for configured off-modal columns (e.g. Status, PrintAt),
   and a new row is created. Then an "item added" message is posted to
   ``notify_channel`` (mentioning the assignee, if set).

Everything tunable lives in ``config.json`` (``project_list``): the list id,
slash command, modal ``fields``, ``column_defaults`` and ``notify_channel``.

Scopes (beyond the calculator's ``commands``-only footprint — see CLAUDE.md):
``files:read`` (``files.info`` reads the List schema), ``lists:read`` +
``lists:write`` (create items), and ``chat:write`` (post the notification).
Reinstall the app after adding them.
"""

import json
import logging

from slack_sdk.errors import SlackApiError

from ui.components import size_select_block
from ui.project_list import CALLBACK_ID, build_create_modal, build_info_modal
from utils.config import load_config
from utils.units import convert

log = logging.getLogger(__name__)

# Block/action ids for the (optional) size-preset selector in the modal.
SIZE_PRESET_BLOCK = "size_preset"
SIZE_PRESET_ACTION = "project_size_select"

# Column types we can render as a modal input. Everything else (created_by,
# last_edited_*, formulas, attachments, …) is read-only/auto and is skipped.
RENDERABLE_TYPES = {
    "text", "number", "date", "select", "email", "phone", "user", "checkbox", "link", "attachment",
    # Slack task-list special columns:
    "todo_assignee", "todo_due_date", "rating",
}


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


# --- column selection / config defaults ------------------------------------

def _norm(name):
    """Normalize a column name for lenient matching (lowercase, no spaces)."""
    return "".join((name or "").lower().split())


def _find_column(columns, key):
    """Match a configured ``column`` key against the schema by id or name."""
    for col in columns:
        if col["id"] == key or _norm(col["name"]) == _norm(key):
            return col
    return None


def _configured_default(col, project_list):
    """Return the configured default value for a column, or None."""
    defaults = project_list.column_defaults
    if col["id"] in defaults:
        return defaults[col["id"]]
    by_name = {_norm(k): v for k, v in defaults.items()}
    return by_name.get(_norm(col["name"]))


def select_columns(columns, project_list):
    """Resolve the modal's columns from ``project_list.fields``.

    Returns enriched column dicts (with ``label`` and ``required`` set) in the
    configured order. Configured fields missing from the schema, or of a type we
    can't render, are logged and skipped. With no ``fields`` configured, falls
    back to auto-rendering every editable column (primary = required).
    """
    if not project_list.fields:
        return [dict(c, required=c["is_primary"]) for c in renderable_columns(columns)]

    chosen = []
    for spec in project_list.fields:
        key = spec["column"]
        col = _find_column(columns, key)
        if col is None:
            log.warning("configured field %r not found in list schema", key)
            continue
        if col["type"] not in RENDERABLE_TYPES:
            log.warning("configured field %r has unrenderable type %r; skipping", key, col["type"])
            continue
        extras = {k: spec[k] for k in ("placeholder", "input", "filetypes", "max_files") if k in spec}
        chosen.append(
            dict(col, label=spec.get("label") or col["name"], required=bool(spec.get("required")), **extras)
        )
    return chosen


def default_fields(columns, project_list, shown_ids):
    """Build ``{id, type, value}`` defaults for columns kept out of the modal."""
    out = []
    for col in columns:
        if col["id"] in shown_ids:
            continue
        value = _configured_default(col, project_list)
        if value is not None:
            out.append({"id": col["id"], "type": col["type"], "value": value})
    return out


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


def _rich_text_has_content(rt):
    """True if a rich_text_input value carries any real content."""
    return any(
        (sub.get("text") or "").strip()
        or sub.get("type") in ("link", "emoji", "user", "usergroup", "channel", "broadcast", "date")
        for el in (rt or {}).get("elements", [])
        for sub in el.get("elements", [])
    )


def _read_input(block_state, ctype):
    """Pull the raw value for one column out of its block state, or None if empty."""
    el = block_state.get("value", {})
    if ctype in ("date", "todo_due_date"):
        return el.get("selected_date") or None
    if ctype in ("user", "todo_assignee"):
        return el.get("selected_user") or None
    if ctype in ("select", "rating"):
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
    if ctype in ("date", "todo_due_date"):
        return {"column_id": col_id, "date": [value]}
    if ctype == "select":
        return {"column_id": col_id, "select": [value]}
    if ctype == "rating":
        return {"column_id": col_id, "rating": [int(float(value))]}
    if ctype in ("user", "todo_assignee"):
        return {"column_id": col_id, "user": [value]}
    if ctype == "email":
        return {"column_id": col_id, "email": [value]}
    if ctype == "phone":
        return {"column_id": col_id, "phone": [value]}
    if ctype == "link":
        return {"column_id": col_id, "link": [{"original_url": value, "display_as_url": True}]}
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
        if col.get("input") == "file":
            continue  # file uploads need the client (permalink) — handled in the cog
        cid, ctype = col["id"], col["type"]
        block_state = state_values.get(cid, {})

        if col.get("input") == "richtext":
            rt = (block_state.get("value", {}) or {}).get("rich_text_value")
            if rt and _rich_text_has_content(rt):
                fields.append({"column_id": cid, "rich_text": [rt]})
            continue

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


def _read_select_value(state_values, block, action):
    try:
        return state_values[block][action]["selected_option"]["value"]
    except (KeyError, TypeError):
        return None


def _uploaded_file_ids(state_values, col_id):
    """File IDs uploaded into a file_input block (empty list if none)."""
    block = state_values.get(col_id, {}).get("value", {}) or {}
    return [f["id"] for f in (block.get("files") or []) if f.get("id")]


def handle_file_column(client, col, state_values):
    """Process a file-upload column. Returns ``(field, thumb)``.

    ``field`` is the ``initial_fields`` entry (None if nothing uploaded):
    ``attachment`` columns store the file IDs directly; ``link``/``text`` store
    the file's Slack permalink (one ``files.info`` call). ``thumb`` is
    ``{"id": file_id}`` when the upload is an image (for the notification card).
    """
    file_ids = _uploaded_file_ids(state_values, col["id"])
    if not file_ids:
        return None, None

    ctype = col["type"]
    if ctype == "attachment":
        # Attachment columns hold files directly; thumb only if the first is an image.
        return {"column_id": col["id"], "attachment": file_ids}, None

    info = {}
    try:
        info = client.files_info(file=file_ids[0])["file"]
    except Exception:
        log.exception("files.info failed for uploaded file %s", file_ids[0])
    permalink = info.get("permalink")
    thumb = {"id": file_ids[0]} if str(info.get("mimetype", "")).startswith("image/") else None

    if not permalink:
        return None, thumb
    if ctype == "link":
        field = {"column_id": col["id"], "link": [{"original_url": permalink, "display_as_url": True}]}
    else:
        field = _field_for(col["id"], "text", permalink)
    return field, thumb


# --- notification ----------------------------------------------------------

def _notification_meta(columns):
    """Pick the columns used to compose the post-create message.

    ``name_col`` = the item-name field (first text column), ``assignee_col`` =
    the user/assignee field (by name, else first user-ish column).
    """
    meta = {}
    name_col = next((c["id"] for c in columns if c["type"] in ("text", "link")), None)
    if name_col:
        meta["name_col"] = name_col
    assignee = next((c["id"] for c in columns if _norm(c["name"]) == "assignee"), None)
    if not assignee:
        assignee = next((c["id"] for c in columns if c["type"] in ("user", "todo_assignee")), None)
    if assignee:
        meta["assignee_col"] = assignee
    return meta


def _thumbnail_accessory(thumb, placeholder_url):
    """Image accessory for the card: the uploaded image, else a placeholder."""
    if thumb and thumb.get("id"):
        return {"type": "image", "slack_file": {"id": thumb["id"]}, "alt_text": "attachment"}
    if placeholder_url:
        return {"type": "image", "image_url": placeholder_url, "alt_text": "no file attached"}
    return None


def build_notification(name, assignee, creator, thumb, placeholder_url):
    """Build the Block Kit 'item created' card (pure)."""
    lines = [f"*{name or 'Untitled'}*"]
    if assignee:
        lines.append(f":bust_in_silhouette: Assignee: <@{assignee}>")
    if creator:
        lines.append(f":pencil: Added by: <@{creator}>")
    section = {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}
    accessory = _thumbnail_accessory(thumb, placeholder_url)
    if accessory:
        section["accessory"] = accessory
    return [
        {"type": "header", "text": {"type": "plain_text", "text": "🆕 New item created"}},
        section,
    ]


def _post_create_notification(client, channel, state_values, meta, creator, thumb, placeholder_url):
    """Post the 'item added' card to the channel."""
    if not channel:
        return
    name = None
    if meta.get("name_col"):
        name = _read_input(state_values.get(meta["name_col"], {}), "text")
    assignee = None
    if meta.get("assignee_col"):
        assignee = _read_input(state_values.get(meta["assignee_col"], {}), "user")

    blocks = build_notification(name, assignee, creator, thumb, placeholder_url)
    try:
        client.chat_postMessage(
            channel=channel, blocks=blocks, text=f"New item added: {name or 'Untitled'}"
        )
    except Exception:
        log.exception("failed to post create notification to %s", channel)


# --- size preset / created-by ----------------------------------------------

def _size_lead_block(pl, columns, shown, extra_meta):
    """Build the size-preset lead block and record its target columns.

    Marks the width/height columns optional (the preset can fill them) and
    stashes their ids/types + unit in ``extra_meta["size"]``. Returns the lead
    blocks list (empty if the feature is off).
    """
    ss = pl.size_select
    if not (ss and ss.get("enabled")):
        return []
    wcol = _find_column(columns, ss.get("width_column", ""))
    hcol = _find_column(columns, ss.get("height_column", ""))
    fill_ids = {c["id"] for c in (wcol, hcol) if c}
    for c in shown:
        if c["id"] in fill_ids:
            c["required"] = False
    extra_meta["size"] = {
        "unit": ss.get("unit", "in"),
        "width_col": {"id": wcol["id"], "type": wcol["type"]} if wcol else None,
        "height_col": {"id": hcol["id"], "type": hcol["type"]} if hcol else None,
    }
    return [
        size_select_block(
            load_config().size_presets,
            "",
            block_id=SIZE_PRESET_BLOCK,
            action_id=SIZE_PRESET_ACTION,
            label="Size preset (fills Width / Height)",
            optional=True,
        )
    ]


def _record_created_by(pl, columns, extra_meta):
    """Stash the user-settable "created by" column (if configured + writable)."""
    if not pl.created_by_column:
        return
    col = _find_column(columns, pl.created_by_column)
    if not col:
        log.warning("created_by_column %r not found in list schema", pl.created_by_column)
        return
    if col["type"] not in ("user", "todo_assignee"):
        log.warning(
            "created_by column %r is type %r (not user-settable); skipping",
            pl.created_by_column, col["type"],
        )
        return
    extra_meta["created_by_col"] = {"id": col["id"], "type": col["type"]}


def apply_size_preset(fields, size_meta, selected_value, size_presets):
    """If a non-custom size is selected, set width/height from it (overriding typed)."""
    if not selected_value or selected_value == "custom":
        return fields
    preset = next((s for s in size_presets if s.value == selected_value), None)
    if not preset or preset.is_custom:
        return fields
    unit = size_meta.get("unit", "in")
    out = list(fields)
    for key, dim_mm in (("width_col", preset.width_mm), ("height_col", preset.height_mm)):
        col = size_meta.get(key)
        if col:
            value = round(convert(dim_mm, "mm", unit), 4)
            out = [f for f in out if f["column_id"] != col["id"]]
            out.append(_field_for(col["id"], col["type"], value))
    return out


def missing_size_error(fields, size_meta):
    """Error dict if width/height ended up unset (neither preset nor typed)."""
    present = {f["column_id"] for f in fields}
    for key in ("width_col", "height_col"):
        col = size_meta.get(key)
        if col and col["id"] not in present:
            return {SIZE_PRESET_BLOCK: "Pick a size, or enter Width and Height below"}
    return {}


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

        columns = parse_columns(file_obj)
        shown = select_columns(columns, pl)
        if not shown:
            client.views_open(
                trigger_id=trigger_id,
                view=build_info_modal(
                    "Error", "None of the configured fields were found in this list."
                ),
            )
            return

        extra_meta = _notification_meta(shown)
        lead_blocks = _size_lead_block(pl, columns, shown, extra_meta)
        _record_created_by(pl, columns, extra_meta)

        hidden_defaults = default_fields(columns, pl, {c["id"] for c in shown})
        client.views_open(
            trigger_id=trigger_id,
            view=build_create_modal(
                shown, pl.list_id, pl.title, hidden_defaults, extra_meta, lead_blocks
            ),
        )

    @app.view(CALLBACK_ID)
    def submit_new_project(ack, body, view, client):
        meta = json.loads(view["private_metadata"])
        state_values = view["state"]["values"]
        fields, errors = extract_fields(state_values, meta["cols"])
        if errors:
            ack(response_action="errors", errors=errors)
            return

        # File-upload columns: resolve uploaded files + grab an image thumbnail.
        thumb = None
        for col in meta["cols"]:
            if col.get("input") == "file":
                field, t = handle_file_column(client, col, state_values)
                if field:
                    fields.append(field)
                if t and not thumb:
                    thumb = t

        # Size preset fills width/height (overrides typed); require they end up set.
        size_meta = meta.get("size")
        if size_meta:
            sel = _read_select_value(state_values, SIZE_PRESET_BLOCK, SIZE_PRESET_ACTION)
            fields = apply_size_preset(fields, size_meta, sel, load_config().size_presets)
            size_err = missing_size_error(fields, size_meta)
            if size_err:
                ack(response_action="errors", errors=size_err)
                return

        # CreatedBy = the person who ran the command, not the bot.
        creator = body.get("user", {}).get("id")
        cb = meta.get("created_by_col")
        if cb and creator:
            fields = [f for f in fields if f["column_id"] != cb["id"]]
            fields.append({"column_id": cb["id"], "user": [creator]})

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
        _post_create_notification(
            client, pl.notify_channel, state_values, meta, creator, thumb, pl.placeholder_image_url
        )

import logging

from utils.units import convert

log = logging.getLogger(__name__)

RENDERABLE_TYPES = {
    "text", "number", "date", "select", "email", "phone", "user", "checkbox", "link", "attachment",
    "todo_assignee", "todo_due_date", "rating",
}


def parse_columns(file_obj):
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


def norm(name):
    return "".join((name or "").lower().split())


def find_column(columns, key):
    for col in columns:
        if col["id"] == key or norm(col["name"]) == norm(key):
            return col
    return None


def _configured_default(col, project_list):
    defaults = project_list.column_defaults
    if col["id"] in defaults:
        return defaults[col["id"]]
    by_name = {norm(k): v for k, v in defaults.items()}
    return by_name.get(norm(col["name"]))


def select_columns(columns, project_list):
    if not project_list.fields:
        return [dict(c, required=c["is_primary"]) for c in renderable_columns(columns)]

    chosen = []
    for spec in project_list.fields:
        key = spec["column"]
        col = find_column(columns, key)
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
    out = []
    for col in columns:
        if col["id"] in shown_ids:
            continue
        value = _configured_default(col, project_list)
        if value is not None:
            out.append({"id": col["id"], "type": col["type"], "value": value})
    return out


def created_by_target(project_list, columns):
    if not project_list.created_by_column:
        return None
    col = find_column(columns, project_list.created_by_column)
    if not col:
        log.warning("created_by_column %r not found in list schema", project_list.created_by_column)
        return None
    if col["type"] not in ("user", "todo_assignee"):
        log.warning(
            "created_by column %r is type %r (not user-settable); skipping",
            project_list.created_by_column, col["type"],
        )
        return None
    return {"id": col["id"], "type": col["type"]}


def size_targets(project_list, columns):
    ss = project_list.size_select
    if not (ss and ss.get("enabled")):
        return None
    wcol = find_column(columns, ss.get("width_column", ""))
    hcol = find_column(columns, ss.get("height_column", ""))
    return {
        "unit": ss.get("unit", "in"),
        "width_col": {"id": wcol["id"], "type": wcol["type"]} if wcol else None,
        "height_col": {"id": hcol["id"], "type": hcol["type"]} if hcol else None,
    }


def size_fill_ids(size_meta):
    return {col["id"] for key in ("width_col", "height_col") if (col := size_meta.get(key))}


def _rich_text(value):
    return [
        {
            "type": "rich_text",
            "elements": [
                {"type": "rich_text_section", "elements": [{"type": "text", "text": value}]}
            ],
        }
    ]


def _rich_text_has_content(rt):
    return any(
        (sub.get("text") or "").strip()
        or sub.get("type") in ("link", "emoji", "user", "usergroup", "channel", "broadcast", "date")
        for el in (rt or {}).get("elements", [])
        for sub in el.get("elements", [])
    )


def read_input(block_state, ctype):
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


def field_for(col_id, ctype, value):
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
    fields = []
    errors = {}
    for col in cols:
        if col.get("input") == "file":
            continue
        cid, ctype = col["id"], col["type"]
        block_state = state_values.get(cid, {})

        if col.get("input") == "richtext":
            rt = (block_state.get("value", {}) or {}).get("rich_text_value")
            if rt and _rich_text_has_content(rt):
                fields.append({"column_id": cid, "rich_text": [rt]})
            continue

        value = read_input(block_state, ctype)

        if ctype == "checkbox":
            fields.append(field_for(cid, ctype, value))
            continue
        if value is None:
            continue
        if ctype == "number":
            try:
                value = float(value)
            except (TypeError, ValueError):
                errors[cid] = "Enter a number"
                continue
        fields.append(field_for(cid, ctype, value))

    return fields, errors


def read_select_value(state_values, block, action):
    try:
        return state_values[block][action]["selected_option"]["value"]
    except (KeyError, TypeError):
        return None


def uploaded_file_ids(state_values, col_id):
    block = state_values.get(col_id, {}).get("value", {}) or {}
    return [f["id"] for f in (block.get("files") or []) if f.get("id")]


def is_image(mimetype):
    return str(mimetype or "").startswith("image/")


def file_field(col, file_ids, permalink):
    if not file_ids:
        return None
    if col["type"] == "attachment":
        return {"column_id": col["id"], "attachment": file_ids}
    if not permalink:
        return None
    if col["type"] == "link":
        return {"column_id": col["id"], "link": [{"original_url": permalink, "display_as_url": True}]}
    return field_for(col["id"], "text", permalink)


def apply_size_preset(fields, size_meta, selected_value, size_presets):
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
            out.append(field_for(col["id"], col["type"], value))
    return out


def size_incomplete(fields, size_meta):
    present = {f["column_id"] for f in fields}
    for key in ("width_col", "height_col"):
        col = size_meta.get(key)
        if col and col["id"] not in present:
            return True
    return False


def notification_meta(columns):
    meta = {}
    name_col = next((c["id"] for c in columns if c["type"] in ("text", "link")), None)
    if name_col:
        meta["name_col"] = name_col
    assignee = next((c["id"] for c in columns if norm(c["name"]) == "assignee"), None)
    if not assignee:
        assignee = next((c["id"] for c in columns if c["type"] in ("user", "todo_assignee")), None)
    if assignee:
        meta["assignee_col"] = assignee
    return meta


def notification_data(state_values, meta):
    name = None
    if meta.get("name_col"):
        name = read_input(state_values.get(meta["name_col"], {}), "text")
    assignee = None
    if meta.get("assignee_col"):
        assignee = read_input(state_values.get(meta["assignee_col"], {}), "user")
    return name, assignee


def item_url(list_url, item_id):
    if not (list_url and item_id):
        return None
    sep = "&" if "?" in list_url else "?"
    return f"{list_url}{sep}record_id={item_id}"


def created_item_id(result):
    item = result.get("item") or result.get("record") or {}
    return item.get("id") or result.get("id")

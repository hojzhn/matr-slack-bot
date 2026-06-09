import json

from services.calculator import calculate_position
from ui.calculator import (
    CALLBACK_ID,
    MARGIN_ACTION_ID,
    ORIGIN_ACTION_ID,
    SIZE_ACTION_ID,
    UNIT_ACTION_ID,
    build_input_modal,
    build_result_modal,
    fmt,
)
from utils.config import load_config
from utils.units import convert


_NUMBER_FIELDS = ("width", "height", "dx", "dy")


def _convert_str(s, from_unit, to_unit):

    if not s:
        return s
    try:
        return fmt(convert(float(s), from_unit, to_unit))
    except (TypeError, ValueError):
        return s


def _selected(state, block, action_id):
    return state[block][action_id]["selected_option"]["value"]


def _num(state, block):
    try:
        return state[block]["value"]["value"]
    except (KeyError, TypeError):
        return None


def _read_form(state):

    values = {}
    for block in ("width", "height", "margin_custom", "dx", "dy"):
        v = _num(state, block)
        if v is not None:
            values[block] = v
    return {
        "selected_unit": _selected(state, "unit", UNIT_ACTION_ID),
        "selected_origin": _selected(state, "origin", ORIGIN_ACTION_ID),
        "selected_size": _selected(state, "size", SIZE_ACTION_ID),
        "selected_margin": _selected(state, "margin", MARGIN_ACTION_ID),
        "values": values,
    }


def extract_values(state_values, config=None):

    config = config or load_config()
    parsed = {}
    errors = {}

    parsed["unit"] = _selected(state_values, "unit", UNIT_ACTION_ID)
    parsed["origin"] = _selected(state_values, "origin", ORIGIN_ACTION_ID)
    unit = parsed["unit"]

    for block in _NUMBER_FIELDS:
        raw = _num(state_values, block)
        try:
            parsed[block] = float(raw)
        except (TypeError, ValueError):
            errors[block] = "Enter a number"

    preset = config.margin_preset(_selected(state_values, "margin", MARGIN_ACTION_ID))
    if preset.is_custom:
        raw = _num(state_values, "margin_custom")
        try:
            parsed["margin_mm"] = convert(float(raw), unit, "mm")
        except (TypeError, ValueError):
            errors["margin_custom"] = "Enter a number"
    else:
        parsed["margin_mm"] = preset.margin_mm

    if "width" in parsed and parsed["width"] <= 0:
        errors["width"] = "Must be greater than 0"
    if "height" in parsed and parsed["height"] <= 0:
        errors["height"] = "Must be greater than 0"
    if parsed.get("margin_mm", 0) < 0:
        errors.setdefault("margin_custom", "Cannot be negative")

    return parsed, errors


def compute_from_state(state_values, config=None):

    config = config or load_config()
    parsed, errors = extract_values(state_values, config)
    if errors:
        return None, errors

    unit = parsed["unit"]
    origin = config.origin(parsed["origin"])
    result = calculate_position(
        width_mm=convert(parsed["width"], unit, "mm"),
        height_mm=convert(parsed["height"], unit, "mm"),
        margin_mm=parsed["margin_mm"],
        delta_x_mm=parsed["dx"],
        delta_y_mm=parsed["dy"],
        x0_mm=origin.x0_mm,
        y0_mm=origin.y0_mm,
    )
    return result, {}


def register(app):
    @app.command("/calc")
    def open_calc(ack, body, client):
        ack()
        client.views_open(trigger_id=body["trigger_id"], view=build_input_modal(load_config()))

    @app.action(UNIT_ACTION_ID)
    def on_unit_change(ack, body, client):

        ack()
        view = body["view"]
        form = _read_form(view["state"]["values"])
        new_unit = form["selected_unit"]
        old_unit = json.loads(view.get("private_metadata") or "{}").get("unit", new_unit)
        if old_unit != new_unit:
            for block in ("width", "height", "margin_custom"):
                if block in form["values"]:
                    form["values"][block] = _convert_str(form["values"][block], old_unit, new_unit)
        client.views_update(view_id=view["id"], view=build_input_modal(load_config(), **form))

    @app.action(SIZE_ACTION_ID)
    def on_size_change(ack, body, client):

        ack()
        view = body["view"]
        form = _read_form(view["state"]["values"])
        size = load_config().size_preset(form["selected_size"])
        if not size.is_custom:
            unit = form["selected_unit"]
            form["values"]["width"] = _convert_str(fmt(size.width_mm), "mm", unit)
            form["values"]["height"] = _convert_str(fmt(size.height_mm), "mm", unit)
        client.views_update(view_id=view["id"], view=build_input_modal(load_config(), **form))

    @app.action(MARGIN_ACTION_ID)
    def on_margin_change(ack, body, client):

        ack()
        view = body["view"]
        form = _read_form(view["state"]["values"])
        client.views_update(view_id=view["id"], view=build_input_modal(load_config(), **form))

    @app.view(CALLBACK_ID)
    def handle_submit(ack, view):
        result, errors = compute_from_state(view["state"]["values"])
        if errors:
            ack(response_action="errors", errors=errors)
            return
        ack(response_action="update", view=build_result_modal(result))

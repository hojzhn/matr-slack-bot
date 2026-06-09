import json

from ui.components import size_select_block

CALLBACK_ID = "calc_submit"


UNIT_ACTION_ID = "unit_select"
ORIGIN_ACTION_ID = "origin_select"
SIZE_ACTION_ID = "size_select"
MARGIN_ACTION_ID = "margin_select"


def fmt(x):

    return f"{x:g}"


def _option(value, label):
    return {"text": {"type": "plain_text", "text": label}, "value": value}


def _unit_label(unit):
    return {"in": "Inches (in)", "mm": "Millimetres (mm)"}[unit]


def _number_input(block_id, label, initial=None):
    element = {"type": "plain_text_input", "action_id": "value"}
    if initial is not None and initial != "":
        element["initial_value"] = str(initial)
    return {
        "type": "input",
        "block_id": block_id,
        "label": {"type": "plain_text", "text": label},
        "element": element,
    }


def _select_block(block_id, action_id, label, options, selected, dispatch=False):
    block = {
        "type": "input",
        "block_id": block_id,
        "label": {"type": "plain_text", "text": label},
        "element": {
            "type": "static_select",
            "action_id": action_id,
            "initial_option": _option(selected.value, selected.label),
            "options": [_option(o.value, o.label) for o in options],
        },
    }
    if dispatch:
        block["dispatch_action"] = True
    return block


def build_input_modal(
    config,
    *,
    selected_unit="in",
    selected_origin=None,
    selected_size=None,
    selected_margin=None,
    values=None,
):

    selected_origin = selected_origin or config.default_origin_value
    selected_size = selected_size or config.default_size_value
    selected_margin = selected_margin or config.default_margin_value
    values = dict(values or {})

    origin = config.origin(selected_origin)
    margin = config.margin_preset(selected_margin)
    u = selected_unit

    dx = values.get("dx", fmt(config.delta_x_mm))
    dy = values.get("dy", fmt(config.delta_y_mm))

    blocks = [
        {
            "type": "input",
            "block_id": "unit",
            "dispatch_action": True,
            "label": {"type": "plain_text", "text": "Units for width / height / custom margin"},
            "element": {
                "type": "radio_buttons",
                "action_id": UNIT_ACTION_ID,
                "initial_option": _option(u, _unit_label(u)),
                "options": [_option("in", _unit_label("in")), _option("mm", _unit_label("mm"))],
            },
        },

        _number_input("width", f"Width ({u})", values.get("width")),

        _number_input("height", f"Height ({u})", values.get("height")),

        size_select_block(
            config.size_presets,
            selected_size,
            block_id="size",
            action_id=SIZE_ACTION_ID,
            label="Size preset",
            dispatch=True,
        ),
    ]

    if margin.is_custom:
        blocks.append(
            _number_input("margin_custom", f"Custom margin ({u})", values.get("margin_custom"))
        )

    blocks += [
        {"type": "divider"},

        _select_block("origin", ORIGIN_ACTION_ID, "Machine origin", config.origins, origin),

        _select_block(
            "margin", MARGIN_ACTION_ID, "Margin", config.margin_presets, margin, dispatch=True
        ),
    ]

    blocks += [
        {"type": "divider"},
        _number_input("dx", "Delta X (mm)", dx),
        _number_input("dy", "Delta Y (mm)", dy),
    ]

    return {
        "type": "modal",
        "callback_id": CALLBACK_ID,

        "private_metadata": json.dumps({"unit": u}),
        "title": {"type": "plain_text", "text": "PrintMon Calculator"},
        "submit": {"type": "plain_text", "text": "Calculate"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }


def build_result_modal(result):
    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": "PrintMon Result"},
        "close": {"type": "plain_text", "text": "Done"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Enter these into PrintMon (mm):*"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*x pos*\n`{result.x_pos_mm:.2f}` mm"},
                    {"type": "mrkdwn", "text": f"*y pos*\n`{result.y_pos_mm:.2f}` mm"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Adj. width*\n`{result.adj_width_mm:.2f}` mm "
                        f"({result.adj_width_in:.2f} in)",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Adj. height*\n`{result.adj_height_mm:.2f}` mm "
                        f"({result.adj_height_in:.2f} in)",
                    },
                ],
            },
        ],
    }

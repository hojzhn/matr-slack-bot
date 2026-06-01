
def _size_option(preset):
    return {"text": {"type": "plain_text", "text": preset.label[:75]}, "value": preset.value}


def size_select_block(
    size_presets,
    selected_value="",
    *,
    block_id="size",
    action_id="size_select",
    label="Size preset",
    optional=False,
    dispatch=False,
):

    selected = next((s for s in size_presets if s.value == selected_value), size_presets[0])
    block = {
        "type": "input",
        "block_id": block_id,
        "optional": optional,
        "label": {"type": "plain_text", "text": label},
        "element": {
            "type": "static_select",
            "action_id": action_id,
            "initial_option": _size_option(selected),
            "options": [_size_option(s) for s in size_presets],
        },
    }
    if dispatch:
        block["dispatch_action"] = True
    return block

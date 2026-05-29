"""Shared, reusable Block Kit components used across more than one modal.

Pure view builders — data in, Block Kit dict out (same rules as the rest of
``ui/``). Take config dataclass objects (e.g. size presets) and render.
"""


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
    """A dropdown of preset sizes.

    Wire ``action_id`` to a block action to auto-fill width/height live (the
    calculator does this with ``dispatch=True``), or just read the choice at
    submit time (the project modal does this with ``dispatch=False``). Takes the
    config ``size_presets`` objects (each with ``.value`` / ``.label``).
    """
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

import json
import logging

from slack_sdk.errors import SlackApiError

from services import project_list as svc
from ui.project_list import (
    CALLBACK_ID,
    DETAILS_ACTION,
    SIZE_INCOMPLETE_MESSAGE,
    SIZE_PRESET_ACTION,
    SIZE_PRESET_BLOCK,
    api_error_message,
    build_create_modal,
    build_info_modal,
    build_notification,
    build_size_preset_block,
)
from utils.config import load_config

log = logging.getLogger(__name__)


def _resolve_file_column(client, col, state_values):
    file_ids = svc.uploaded_file_ids(state_values, col["id"])
    if not file_ids:
        return None, None
    if col["type"] == "attachment":
        return svc.file_field(col, file_ids, None), None
    info = {}
    try:
        info = client.files_info(file=file_ids[0])["file"]
    except Exception:
        log.exception("files.info failed for uploaded file %s", file_ids[0])
    thumb = {"id": file_ids[0]} if svc.is_image(info.get("mimetype", "")) else None
    return svc.file_field(col, file_ids, info.get("permalink")), thumb


def _post_notification(client, channel, state_values, meta, creator, thumb, placeholder_url, item_url):
    if not channel:
        return
    name, assignee = svc.notification_data(state_values, meta)
    blocks = build_notification(name, assignee, creator, thumb, placeholder_url, item_url)
    try:
        client.chat_postMessage(
            channel=channel, blocks=blocks, text=f"New item added: {name or 'Untitled'}"
        )
    except Exception:
        log.exception("failed to post create notification to %s", channel)


def register(app):
    pl = load_config().project_list
    if not pl:
        return

    @app.command(pl.command)
    def open_new_project(ack, body, client):
        ack()
        trigger_id = body["trigger_id"]
        try:
            file_obj = client.files_info(file=pl.list_id)["file"]
        except SlackApiError as exc:
            log.exception("files.info failed for list %s", pl.list_id)
            msg = api_error_message(exc.response.get("error"), exc.response.get("needed"))
            client.views_open(trigger_id=trigger_id, view=build_info_modal("Error", msg))
            return
        except Exception as exc:
            log.exception("files.info failed for list %s", pl.list_id)
            client.views_open(
                trigger_id=trigger_id,
                view=build_info_modal("Error", f"Couldn't load the list:\n`{exc}`"),
            )
            return

        log.info("list %s metadata: %s", pl.list_id, json.dumps(file_obj.get("list_metadata", {}))[:3000])

        columns = svc.parse_columns(file_obj)
        shown = svc.select_columns(columns, pl)
        if not shown:
            client.views_open(
                trigger_id=trigger_id,
                view=build_info_modal("Error", "None of the configured fields were found in this list."),
            )
            return

        extra_meta = svc.notification_meta(shown)
        list_url = file_obj.get("permalink") or file_obj.get("url_private")
        if list_url:
            extra_meta["list_url"] = list_url

        lead_blocks = []
        size = svc.size_targets(pl, columns)
        if size:
            fill_ids = svc.size_fill_ids(size)
            for c in shown:
                if c["id"] in fill_ids:
                    c["required"] = False
            extra_meta["size"] = size
            lead_blocks = [build_size_preset_block(load_config().size_presets)]

        created_by = svc.created_by_target(pl, columns)
        if created_by:
            extra_meta["created_by_col"] = created_by

        hidden_defaults = svc.default_fields(columns, pl, {c["id"] for c in shown})
        client.views_open(
            trigger_id=trigger_id,
            view=build_create_modal(shown, pl.list_id, pl.title, hidden_defaults, extra_meta, lead_blocks),
        )

    @app.view(CALLBACK_ID)
    def submit_new_project(ack, body, view, client):
        meta = json.loads(view["private_metadata"])
        state_values = view["state"]["values"]

        fields, errors = svc.extract_fields(state_values, meta["cols"])
        if errors:
            ack(response_action="errors", errors=errors)
            return

        thumb = None
        for col in meta["cols"]:
            if col.get("input") == "file":
                field, t = _resolve_file_column(client, col, state_values)
                if field:
                    fields.append(field)
                if t and not thumb:
                    thumb = t

        size_meta = meta.get("size")
        if size_meta:
            sel = svc.read_select_value(state_values, SIZE_PRESET_BLOCK, SIZE_PRESET_ACTION)
            fields = svc.apply_size_preset(fields, size_meta, sel, load_config().size_presets)
            if svc.size_incomplete(fields, size_meta):
                ack(response_action="errors", errors={SIZE_PRESET_BLOCK: SIZE_INCOMPLETE_MESSAGE})
                return

        creator = body.get("user", {}).get("id")
        cb = meta.get("created_by_col")
        if cb and creator:
            fields = [f for f in fields if f["column_id"] != cb["id"]]
            fields.append({"column_id": cb["id"], "user": [creator]})

        for hidden in meta.get("hidden", []):
            try:
                fields.append(svc.field_for(hidden["id"], hidden["type"], hidden["value"]))
            except (ValueError, TypeError):
                log.warning("skipping invalid default for column %s", hidden["id"])

        try:
            result = client.slackLists_items_create(list_id=meta["list_id"], initial_fields=fields)
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
            view=build_info_modal("Created!", "Your project was added to the list."),
        )

        item_id = svc.created_item_id(result)
        url = svc.item_url(meta.get("list_url"), item_id) or meta.get("list_url")
        _post_notification(
            client, pl.notify_channel, state_values, meta, creator, thumb, pl.placeholder_image_url, url
        )

    @app.action(DETAILS_ACTION)
    def _ack_details_link(ack):
        ack()

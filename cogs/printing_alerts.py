import logging
import threading

from repo import db, printing_alerts_repo
from services import printing_alerts as svc
from ui.order_alerts import build_job_alert_message
from utils.config import load_config

log = logging.getLogger(__name__)


def _drain(client, cfg):

    try:
        rows = printing_alerts_repo.fetch_pending_printing()
    except Exception:
        log.exception("printing_alerts: poll query failed")
        return

    posted = []
    try:
        for row in rows:
            desc = svc.describe_printing(row)
            client.chat_postMessage(
                channel=cfg.channel,
                blocks=build_job_alert_message(desc),
                text=svc.fallback_text(desc),
            )
            posted.append((row["job_id"], row["event"]))
    except Exception:
        log.exception("printing_alerts: failed to post an alert; will retry unposted rows next tick")
    finally:

        if posted:
            try:
                printing_alerts_repo.mark_printing_notified(posted)
            except Exception:
                log.exception("printing_alerts: posted %d alert(s) but failed to flag them", len(posted))


def _poll_loop(client, cfg, stop):

    while not stop.wait(cfg.poll_seconds):
        _drain(client, cfg)


def register(app):
    cfg = load_config().printing_alerts
    if not cfg or not cfg.enabled:
        return
    if not db.is_configured():
        log.warning("printing_alerts: DATABASE_URL not set; printing poller disabled")
        return
    if not cfg.channel:
        log.warning("printing_alerts: no channel configured; printing poller disabled")
        return
    try:
        db.healthcheck()
    except Exception:
        log.exception("printing_alerts: database unreachable; printing poller disabled")
        return

    stop = threading.Event()
    thread = threading.Thread(
        target=_poll_loop,
        args=(app.client, cfg, stop),
        name="printing-alert-poller",
        daemon=True,
    )
    thread.start()
    log.info(
        "printing_alerts: polling job_tracking (printing milestones) every %ss -> channel %s",
        cfg.poll_seconds, cfg.channel,
    )

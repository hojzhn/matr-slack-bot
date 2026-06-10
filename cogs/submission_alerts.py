import logging
import threading

from repo import db, submission_alerts_repo
from services import submission_alerts as svc
from ui.submission_alerts import build_submission_alert_message
from utils.config import load_config

log = logging.getLogger(__name__)


def _drain(client, cfg):

    try:
        rows = submission_alerts_repo.fetch_pending_submissions()
    except Exception:
        log.exception("submission_alerts: poll query failed")
        return

    posted = []
    try:
        for row in rows:
            desc = svc.describe_submission(row)
            client.chat_postMessage(
                channel=cfg.channel,
                blocks=build_submission_alert_message(desc),
                text=svc.fallback_text(desc),
            )
            posted.append(row["submission_id"])
    except Exception:
        log.exception("submission_alerts: failed to post an alert; will retry unposted rows next tick")
    finally:

        if posted:
            try:
                submission_alerts_repo.mark_submissions_notified(posted)
            except Exception:
                log.exception("submission_alerts: posted %d submission(s) but failed to flag them", len(posted))


def _poll_loop(client, cfg, stop):

    while not stop.wait(cfg.poll_seconds):
        _drain(client, cfg)


def register(app):
    cfg = load_config().submission_alerts
    if not cfg or not cfg.enabled:
        return
    if not db.is_configured():
        log.warning("submission_alerts: DATABASE_URL not set; quote-request poller disabled")
        return
    if not cfg.channel:
        log.warning("submission_alerts: no channel configured; quote-request poller disabled")
        return
    try:
        db.healthcheck()
    except Exception:
        log.exception("submission_alerts: database unreachable; quote-request poller disabled")
        return

    stop = threading.Event()
    thread = threading.Thread(
        target=_poll_loop,
        args=(app.client, cfg, stop),
        name="submission-alert-poller",
        daemon=True,
    )
    thread.start()
    log.info(
        "submission_alerts: polling submissions every %ss -> channel %s",
        cfg.poll_seconds, cfg.channel,
    )

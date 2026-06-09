import logging
import threading

from repo import db, job_alerts_repo
from services import job_alerts as svc
from ui.job_alerts import build_job_alert_message
from utils.config import load_config

log = logging.getLogger(__name__)


def _drain(client, cfg):

    try:
        rows = job_alerts_repo.fetch_pending_jobs()
    except Exception:
        log.exception("job_alerts: poll query failed")
        return

    posted = []
    try:
        for row in rows:
            desc = svc.describe_job(row)
            client.chat_postMessage(
                channel=cfg.channel,
                blocks=build_job_alert_message(desc),
                text=svc.fallback_text(desc),
            )
            posted.append(row["job_id"])
    except Exception:
        log.exception("job_alerts: failed to post an alert; will retry unposted rows next tick")
    finally:

        if posted:
            try:
                job_alerts_repo.mark_jobs_notified(posted)
            except Exception:
                log.exception("job_alerts: posted %d job(s) but failed to flag them", len(posted))


def _poll_loop(client, cfg, stop):

    while not stop.wait(cfg.poll_seconds):
        _drain(client, cfg)


def register(app):
    cfg = load_config().job_alerts
    if not cfg or not cfg.enabled:
        return
    if not db.is_configured():
        log.warning("job_alerts: DATABASE_URL not set; new-job poller disabled")
        return
    if not cfg.channel:
        log.warning("job_alerts: no channel configured; new-job poller disabled")
        return
    try:
        db.healthcheck()
    except Exception:
        log.exception("job_alerts: database unreachable; new-job poller disabled")
        return

    stop = threading.Event()
    thread = threading.Thread(
        target=_poll_loop,
        args=(app.client, cfg, stop),
        name="new-job-alert-poller",
        daemon=True,
    )
    thread.start()
    log.info(
        "job_alerts: polling job_tracking every %ss -> channel %s",
        cfg.poll_seconds, cfg.channel,
    )

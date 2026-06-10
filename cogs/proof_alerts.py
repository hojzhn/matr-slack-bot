import logging
import threading

from repo import proof_alerts_repo, db
from services import proof_alerts as svc
from ui.proof_alerts import build_alert_message
from utils.config import load_config

log = logging.getLogger(__name__)


def _drain(client, cfg):

    try:
        rows = proof_alerts_repo.fetch_pending()
    except Exception:
        log.exception("proof_alerts: poll query failed")
        return

    posted = []
    try:
        for row in rows:
            desc = svc.describe_proof(row)
            client.chat_postMessage(
                channel=cfg.channel,
                blocks=build_alert_message(desc),
                text=svc.fallback_text(desc),
            )
            posted.append(row["proof_id"])
    except Exception:
        log.exception("proof_alerts: failed to post an alert; will retry unposted rows next tick")
    finally:

        if posted:
            try:
                proof_alerts_repo.mark_notified(posted)
            except Exception:
                log.exception("proof_alerts: posted %d proof(s) but failed to flag them", len(posted))


def _poll_loop(client, cfg, stop):

    while not stop.wait(cfg.poll_seconds):
        _drain(client, cfg)


def register(app):
    cfg = load_config().proof_alerts
    if not cfg or not cfg.enabled:
        return
    if not db.is_configured():
        log.warning("proof_alerts: DATABASE_URL not set; alert poller disabled")
        return
    if not cfg.channel:
        log.warning("proof_alerts: no channel configured; alert poller disabled")
        return
    try:
        db.healthcheck()
    except Exception:
        log.exception("proof_alerts: database unreachable; alert poller disabled")
        return

    stop = threading.Event()
    thread = threading.Thread(
        target=_poll_loop,
        args=(app.client, cfg, stop),
        name="proof-alert-poller",
        daemon=True,
    )
    thread.start()
    log.info(
        "proof_alerts: polling order_proofs every %ss -> channel %s",
        cfg.poll_seconds, cfg.channel,
    )

"""Proof-change alert poller.

A background daemon thread polls ``order_proofs`` every ``poll_seconds`` for rows
that changed (``slack_notified`` is not true). It posts each to the configured
Slack channel, then sets ``slack_notified`` true so the row doesn't re-alert. A DB
trigger (``order_proofs_reset_notified``) re-arms the flag on any real change, so
every proof update produces one alert.

Delivery is at-least-once: the flag is set per row only after its message posts,
so a crash mid-batch re-sends rather than drops.

The cog degrades gracefully: if ``DATABASE_URL`` is unset, alerts are disabled in
config, or no channel is set, it logs and does nothing — the rest of the bot runs
normally.
"""

import logging
import threading

from repo import alerts_repo, db
from services import alerts as svc
from ui.alerts import build_alert_message
from utils.config import load_config

log = logging.getLogger(__name__)


def _drain(client, cfg):
    """Post all currently-pending approved rows and flag the ones we posted."""
    try:
        rows = alerts_repo.fetch_pending()
    except Exception:
        log.exception("alerts: poll query failed")
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
        log.exception("alerts: failed to post an alert; will retry unposted rows next tick")
    finally:
        # Flag whatever we managed to post, so it isn't re-sent.
        if posted:
            try:
                alerts_repo.mark_notified(posted)
            except Exception:
                log.exception("alerts: posted %d proof(s) but failed to flag them", len(posted))


def _poll_loop(client, cfg, stop):
    # stop.wait returns True when set (shutdown), False on timeout (next tick).
    while not stop.wait(cfg.poll_seconds):
        _drain(client, cfg)


def register(app):
    cfg = load_config().alerts
    if not cfg or not cfg.enabled:
        return
    if not db.is_configured():
        log.warning("alerts: DATABASE_URL not set; alert poller disabled")
        return
    if not cfg.channel:
        log.warning("alerts: no channel configured; alert poller disabled")
        return
    try:
        db.healthcheck()
    except Exception:
        log.exception("alerts: database unreachable; alert poller disabled")
        return

    stop = threading.Event()
    thread = threading.Thread(
        target=_poll_loop,
        args=(app.client, cfg, stop),
        name="job-approval-alert-poller",
        daemon=True,
    )
    thread.start()
    log.info(
        "alerts: polling order_proofs every %ss -> channel %s",
        cfg.poll_seconds, cfg.channel,
    )

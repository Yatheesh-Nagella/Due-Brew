import logging
import signal
import threading

from due_brew.config import get_settings
from due_brew.database import SessionLocal
from due_brew.emails.sender import get_sender
from due_brew.notifier.tick import run_tick

log = logging.getLogger(__name__)


def tick() -> None:
    """One pass of the notifier: occurrences, reminders, retries, heartbeat."""
    with SessionLocal() as db:
        run_tick(db, get_sender())


def run_forever(stop: threading.Event) -> None:
    settings = get_settings()
    interval = settings.notifier_interval_seconds
    mode = "DRY RUN (logging, not sending)" if settings.notifier_dry_run else f"SMTP via {settings.smtp_host}"
    log.info("notifier started; ticking every %ss; %s", interval, mode)
    while not stop.is_set():
        try:
            tick()
        except Exception:
            # A bad tick must not kill the worker; the next one retries.
            log.exception("tick failed")
        stop.wait(interval)
    log.info("notifier stopped")


def install_signal_handlers(stop: threading.Event) -> None:
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())

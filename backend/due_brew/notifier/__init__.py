import logging
import signal
import threading

from due_brew import heartbeat
from due_brew.config import get_settings
from due_brew.database import SessionLocal

log = logging.getLogger(__name__)


def tick() -> None:
    """One pass of the notifier. M0: heartbeat only; reminders arrive in M3."""
    with SessionLocal() as db:
        heartbeat.beat(db)


def run_forever(stop: threading.Event) -> None:
    interval = get_settings().notifier_interval_seconds
    log.info("notifier started; ticking every %ss", interval)
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

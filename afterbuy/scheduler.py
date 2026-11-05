from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Callable

log = logging.getLogger(__name__)


def next_run_time(run_at: str, now: datetime | None = None) -> datetime:
    now = now or datetime.now()
    hour, minute = (int(x) for x in run_at.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def run_daily(run_at: str, job: Callable[[], object], stop: threading.Event | None = None) -> None:
    """Pokreće `job` svaki dan u `run_at` (lokalno vrijeme, format HH:MM)."""
    stop = stop or threading.Event()
    while not stop.is_set():
        target = next_run_time(run_at)
        log.info("Sljedeća pretraga: %s", target.strftime("%d.%m.%Y. %H:%M"))
        if stop.wait((target - datetime.now()).total_seconds()):
            break
        try:
            job()
        except Exception:
            log.exception("Dnevna pretraga nije uspjela")

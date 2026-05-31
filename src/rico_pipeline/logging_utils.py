"""Structured logging with run_id on every line."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

_run_id: ContextVar[str | None] = ContextVar("run_id", default=None)


class RunIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _run_id.get() or "-"
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s run_id=%(run_id)s %(levelname)s %(name)s — %(message)s")
    )
    handler.addFilter(RunIdFilter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def set_run_id(run_id: str) -> None:
    _run_id.set(run_id)


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)

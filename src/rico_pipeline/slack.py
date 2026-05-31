"""Slack notifications — failures must not fail the pipeline."""

from __future__ import annotations

import json

import requests

from rico_pipeline.config import SLACK_WEBHOOK_URL
from rico_pipeline.logging_utils import get_logger

log = get_logger(__name__)


def _post(text: str) -> None:
    if not SLACK_WEBHOOK_URL:
        log.info("Slack skipped (no webhook): %s", text[:120])
        return
    try:
        resp = requests.post(
            SLACK_WEBHOOK_URL,
            data=json.dumps({"text": text}),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as exc:
        log.warning("Slack notification failed: %s", exc)


def notify_started(run_id: str, limit: int, trigger: str) -> None:
    _post(f":rocket: *RICO pipeline started*\nrun_id=`{run_id}` LIMIT={limit} trigger={trigger}")


def notify_audit_failed(run_id: str, details: str) -> None:
    _post(
        f":rotating_light: *AUDIT FAILED — pipeline halted*\n"
        f"run_id=`{run_id}`\n"
        f"Duplicates:\n```{details}```\n"
        f"Check Airflow task logs for `audit`."
    )


def notify_finished(run_id: str, status: str, duration_s: float, summary: str) -> None:
    emoji = ":white_check_mark:" if status == "succeeded" else ":x:"
    _post(
        f"{emoji} *RICO pipeline {status}*\n"
        f"run_id=`{run_id}` duration={duration_s:.1f}s\n"
        f"```{summary}```"
    )

"""Pipeline run lifecycle and shared context."""

from __future__ import annotations

import hashlib
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from rico_pipeline.config import (
    CLIP_MODEL_VERSION,
    OLLAMA_MODEL,
    PROMPT_VERSION,
    SBERT_MODEL_VERSION,
)
from rico_pipeline.db import execute, fetch_all, fetch_one
from rico_pipeline.logging_utils import get_logger, set_run_id

log = get_logger(__name__)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


@dataclass
class RunContext:
    run_id: str
    dag_run_id: str
    limit: int
    trigger_type: str

    @classmethod
    def start(cls, dag_run_id: str, limit: int, trigger_type: str = "manual") -> "RunContext":
        run_id = str(uuid.uuid4())
        ctx = cls(run_id=run_id, dag_run_id=dag_run_id, limit=limit, trigger_type=trigger_type)
        set_run_id(run_id)
        execute(
            """
            INSERT INTO pipeline_runs (
                run_id, dag_run_id, status, limit_param, git_sha,
                clip_version, sbert_version, llm_model, prompt_version, trigger_type
            ) VALUES (%s, %s, 'running', %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                run_id,
                dag_run_id,
                limit,
                git_sha(),
                CLIP_MODEL_VERSION,
                SBERT_MODEL_VERSION,
                OLLAMA_MODEL,
                PROMPT_VERSION,
                trigger_type,
            ),
        )
        log.info("pipeline run started limit=%s dag_run_id=%s", limit, dag_run_id)
        return ctx

    def finish(self, status: str) -> None:
        execute(
            """
            UPDATE pipeline_runs SET status = %s, ended_at = %s WHERE run_id = %s
            """,
            (status, datetime.now(timezone.utc), self.run_id),
        )
        log.info("pipeline run finished status=%s", status)


def record_metric(run_id: str, name: str, value: float | None = None, text: str | None = None) -> None:
    execute(
        """
        INSERT INTO pipeline_metrics (run_id, metric_name, metric_value, metric_text)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (run_id, metric_name) DO UPDATE
        SET metric_value = EXCLUDED.metric_value, metric_text = EXCLUDED.metric_text
        """,
        (run_id, name, value, text),
    )


def screen_ids_for_run(run_id: str) -> list[int]:
    rows = fetch_all("SELECT screen_id FROM screens_metadata WHERE run_id = %s ORDER BY screen_id", (run_id,))
    return [r[0] for r in rows]

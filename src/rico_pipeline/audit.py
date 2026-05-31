"""Duplicate-detection audit — circuit breaker."""

from __future__ import annotations

import json

from rico_pipeline.db import execute, fetch_all
from rico_pipeline.logging_utils import get_logger
from rico_pipeline.run_context import RunContext

log = get_logger(__name__)


def run_audit(ctx: RunContext) -> dict:
    dup_embeddings = fetch_all(
        """
        SELECT screen_id, model_name, model_version, embedding_kind, COUNT(*) AS n
        FROM screens_embeddings
        GROUP BY screen_id, model_name, model_version, embedding_kind
        HAVING COUNT(*) > 1
        """
    )
    dup_metadata_run = fetch_all(
        """
        SELECT screen_id, COUNT(*) AS n
        FROM screens_metadata
        WHERE run_id = %s
        GROUP BY screen_id
        HAVING COUNT(*) > 1
        """,
        (ctx.run_id,),
    )
    passed = not dup_embeddings and not dup_metadata_run
    details = {
        "duplicate_embeddings": [list(r) for r in dup_embeddings],
        "duplicate_metadata_in_run": [list(r) for r in dup_metadata_run],
    }
    execute(
        """
        INSERT INTO audit_results (run_id, audit_name, passed, details)
        VALUES (%s, 'duplicate_detection', %s, %s::jsonb)
        """,
        (ctx.run_id, passed, json.dumps(details)),
    )
    if not passed:
        msg = json.dumps(details, indent=2)
        log.error("AUDIT FAILED — duplicates found:\n%s", msg)
        raise RuntimeError(f"Audit duplicate_detection failed:\n{msg}")
    log.info("audit passed")
    return {"passed": True, "details": details}

"""Load extraction results into Postgres."""

from __future__ import annotations

import json

from rico_pipeline.db import get_conn
from rico_pipeline.logging_utils import get_logger
from rico_pipeline.minio_client import get_bytes
from rico_pipeline.run_context import RunContext, screen_ids_for_run

log = get_logger(__name__)

UPDATE_EXTRACTION = """
UPDATE screens_metadata
SET extraction_payload = %s,
    prompt_version = %s,
    confidence = %s,
    run_id = %s,
    source_fingerprint = %s,
    updated_at = NOW()
WHERE screen_id = %s
"""

INSERT_REVIEW = """
INSERT INTO screens_review_queue (screen_id, reason, raw_output, run_id, source_fingerprint)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING
"""


def run_load(ctx: RunContext) -> dict:
    screen_ids = screen_ids_for_run(ctx.run_id)
    loaded = 0
    for sid in screen_ids:
        payload = json.loads(get_bytes(f"screens/{sid}.extraction.json"))
        with get_conn() as conn, conn.cursor() as cur:
            if payload.get("needs_review"):
                cur.execute(
                    """
                    INSERT INTO screens_review_queue (screen_id, reason, raw_output, run_id, source_fingerprint)
                    SELECT %s, %s, %s, %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM screens_review_queue
                        WHERE screen_id = %s AND run_id = %s
                    )
                    """,
                    (
                        sid,
                        "llm_extraction_failed",
                        payload.get("raw_output"),
                        ctx.run_id,
                        payload["source_fingerprint"],
                        sid,
                        ctx.run_id,
                    ),
                )
            else:
                cur.execute(
                    UPDATE_EXTRACTION,
                    (
                        json.dumps(payload["body"]),
                        payload["prompt_version"],
                        payload["confidence"],
                        ctx.run_id,
                        payload["source_fingerprint"],
                        sid,
                    ),
                )
                loaded += 1
            conn.commit()
    log.info("load complete rows_out=%s", loaded)
    return {"rows_in": len(screen_ids), "rows_out": loaded}

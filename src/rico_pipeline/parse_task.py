"""Parse view hierarchies and store flat text in MinIO."""

from __future__ import annotations

from rico_pipeline.logging_utils import get_logger
from rico_pipeline.minio_client import get_bytes, put_bytes
from rico_pipeline.parse import parse_hierarchy, text_representation
from rico_pipeline.run_context import RunContext, screen_ids_for_run, sha256_text

log = get_logger(__name__)


def run_parse(ctx: RunContext) -> dict:
    screen_ids = screen_ids_for_run(ctx.run_id)
    for sid in screen_ids:
        raw = get_bytes(f"screens/{sid}.json").decode("utf-8")
        text = text_representation(parse_hierarchy(raw))
        key = f"screens/{sid}.text.txt"
        put_bytes(key, text.encode("utf-8"), "text/plain")
        log.info("parsed screen %s text_len=%s", sid, len(text))
    log.info("parse complete rows_out=%s", len(screen_ids))
    return {"rows_in": len(screen_ids), "rows_out": len(screen_ids)}

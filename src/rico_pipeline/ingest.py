"""Ingest screens from HuggingFace / local parquet into MinIO + Postgres."""

from __future__ import annotations

import itertools
import os
from io import BytesIO

from datasets import load_dataset
from PIL import Image

from rico_pipeline.config import PARQUET_PATH
from rico_pipeline.db import get_conn
from rico_pipeline.logging_utils import get_logger
from rico_pipeline.minio_client import put_bytes
from rico_pipeline.run_context import RunContext, sha256_bytes

log = get_logger(__name__)

UPSERT_METADATA = """
INSERT INTO screens_metadata (
    screen_id, app_package, category, png_path, hierarchy_json_path,
    run_id, source_fingerprint
) VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (screen_id) DO UPDATE SET
    app_package = EXCLUDED.app_package,
    category = EXCLUDED.category,
    png_path = EXCLUDED.png_path,
    hierarchy_json_path = EXCLUDED.hierarchy_json_path,
    run_id = EXCLUDED.run_id,
    source_fingerprint = EXCLUDED.source_fingerprint,
    updated_at = NOW()
"""


def _load_dataset():
    if os.path.exists(PARQUET_PATH):
        log.info("loading local parquet %s", PARQUET_PATH)
        return load_dataset("parquet", data_files={"train": PARQUET_PATH}, split="train")
    return load_dataset(
        "rootsautomation/RICO-Screen2Words",
        split="train",
        streaming=True,
        trust_remote_code=True,
    )


def run_ingest(ctx: RunContext) -> dict:
    ds = _load_dataset()
    count = 0
    for row in itertools.islice(ds, max(ctx.limit * 40, 200)):
        if count >= ctx.limit:
            break
        sid = int(row["screenId"])
        png_buf = BytesIO()
        row["image"].save(png_buf, format="PNG")
        png_bytes = png_buf.getvalue()
        hier_bytes = row["view_hierarchy"].encode("utf-8")
        fingerprint = sha256_bytes(png_bytes)

        png_key = f"screens/{sid}.png"
        json_key = f"screens/{sid}.json"
        put_bytes(png_key, png_bytes, "image/png")
        put_bytes(json_key, hier_bytes, "application/json")

        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                UPSERT_METADATA,
                (sid, row["app_package_name"], row["category"], png_key, json_key, ctx.run_id, fingerprint),
            )
            conn.commit()
        count += 1
        log.info("ingested screen %s category=%r", sid, row["category"])

    log.info("ingest complete rows_out=%s", count)
    return {"rows_out": count}

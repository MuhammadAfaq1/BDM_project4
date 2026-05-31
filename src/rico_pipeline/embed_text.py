"""SBERT text embeddings."""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from rico_pipeline.config import SBERT_MODEL_VERSION, SBERT_PATH
from rico_pipeline.db import get_conn
from rico_pipeline.logging_utils import get_logger
from rico_pipeline.minio_client import get_bytes
from rico_pipeline.run_context import RunContext, screen_ids_for_run, sha256_text

log = get_logger(__name__)

_sbert = None

UPSERT_EMB = """
INSERT INTO screens_embeddings (
    screen_id, model_name, model_version, embedding_kind, vector, run_id, source_fingerprint
) VALUES (%s, %s, %s, 'text', %s, %s, %s)
ON CONFLICT (screen_id, model_name, model_version, embedding_kind) DO UPDATE SET
    vector = EXCLUDED.vector,
    run_id = EXCLUDED.run_id,
    source_fingerprint = EXCLUDED.source_fingerprint
"""


def _get_sbert() -> SentenceTransformer:
    global _sbert
    if _sbert is None:
        log.info("loading SBERT from %s", SBERT_PATH)
        _sbert = SentenceTransformer(SBERT_PATH)
    return _sbert


def run_embed_text(ctx: RunContext) -> dict:
    screen_ids = screen_ids_for_run(ctx.run_id)
    if not screen_ids:
        return {"rows_out": 0}
    sbert = _get_sbert()
    texts, fps = [], []
    for sid in screen_ids:
        text = get_bytes(f"screens/{sid}.text.txt").decode("utf-8")
        texts.append(text)
        fps.append(sha256_text(text))
    vecs = sbert.encode(texts, normalize_embeddings=True).astype("float32")

    with get_conn() as conn, conn.cursor() as cur:
        for sid, vec, fp in zip(screen_ids, vecs, fps, strict=True):
            cur.execute(
                UPSERT_EMB,
                (sid, "sentence-transformers", SBERT_MODEL_VERSION, vec, ctx.run_id, fp),
            )
        conn.commit()
    log.info("embed_text complete rows_out=%s", len(screen_ids))
    return {"rows_in": len(screen_ids), "rows_out": len(screen_ids)}

"""CLIP image embeddings."""

from __future__ import annotations

from io import BytesIO

import numpy as np
import open_clip
import torch
from PIL import Image

from rico_pipeline.config import CLIP_ARCH, CLIP_MODEL_VERSION, CLIP_WEIGHTS_PATH
from rico_pipeline.db import get_conn
from rico_pipeline.logging_utils import get_logger
from rico_pipeline.minio_client import get_bytes
from rico_pipeline.run_context import RunContext, screen_ids_for_run, sha256_bytes

log = get_logger(__name__)

_model = None
_preprocess = None

UPSERT_EMB = """
INSERT INTO screens_embeddings (
    screen_id, model_name, model_version, embedding_kind, vector, run_id, source_fingerprint
) VALUES (%s, %s, %s, 'image', %s, %s, %s)
ON CONFLICT (screen_id, model_name, model_version, embedding_kind) DO UPDATE SET
    vector = EXCLUDED.vector,
    run_id = EXCLUDED.run_id,
    source_fingerprint = EXCLUDED.source_fingerprint
"""


def _get_clip():
    global _model, _preprocess
    if _model is None:
        log.info("loading CLIP from %s", CLIP_WEIGHTS_PATH)
        _model, _, _preprocess = open_clip.create_model_and_transforms(
            CLIP_ARCH, pretrained=CLIP_WEIGHTS_PATH
        )
        _model.eval()
    return _model, _preprocess


def run_embed_image(ctx: RunContext) -> dict:
    screen_ids = screen_ids_for_run(ctx.run_id)
    if not screen_ids:
        return {"rows_out": 0}
    model, preprocess = _get_clip()
    batch, fps = [], []
    for sid in screen_ids:
        png = get_bytes(f"screens/{sid}.png")
        fps.append(sha256_bytes(png))
        img = Image.open(BytesIO(png)).convert("RGB")
        batch.append(preprocess(img))
    tensor = torch.stack(batch)
    with torch.no_grad():
        vecs = model.encode_image(tensor)
        vecs = vecs / vecs.norm(dim=-1, keepdim=True)
    arr = vecs.cpu().numpy().astype("float32")

    with get_conn() as conn, conn.cursor() as cur:
        for sid, vec, fp in zip(screen_ids, arr, fps, strict=True):
            cur.execute(
                UPSERT_EMB,
                (sid, "open-clip", CLIP_MODEL_VERSION, vec, ctx.run_id, fp),
            )
        conn.commit()
    log.info("embed_image complete rows_out=%s", len(screen_ids))
    return {"rows_in": len(screen_ids), "rows_out": len(screen_ids)}

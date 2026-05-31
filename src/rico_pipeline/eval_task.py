"""Recall@k evaluation."""

from __future__ import annotations

from rico_pipeline.config import SBERT_MODEL_VERSION
from rico_pipeline.db import get_conn
from rico_pipeline.logging_utils import get_logger
from rico_pipeline.minio_client import get_bytes
from rico_pipeline.run_context import RunContext, record_metric, screen_ids_for_run
from rico_pipeline.embed_text import _get_sbert

log = get_logger(__name__)

TEXT_NEAREST_SQL = """
    SELECT screen_id
    FROM screens_embeddings
    WHERE embedding_kind = 'text' AND model_version = %s
    ORDER BY vector <-> %s::vector
    LIMIT %s
"""


def _recall_at_k(screen_ids: list[int], queries: list[tuple[int, str]], k: int) -> float:
    sbert = _get_sbert()
    hits = 0
    with get_conn() as conn, conn.cursor() as cur:
        for expected_id, query in queries:
            qvec = sbert.encode([query], normalize_embeddings=True).astype("float32")[0]
            cur.execute(TEXT_NEAREST_SQL, (SBERT_MODEL_VERSION, qvec, k))
            top = [r[0] for r in cur.fetchall()]
            if expected_id in top:
                hits += 1
    return hits / len(queries) if queries else 0.0


def run_eval(ctx: RunContext) -> dict:
    screen_ids = screen_ids_for_run(ctx.run_id)
    text_reps = {
        sid: get_bytes(f"screens/{sid}.text.txt").decode("utf-8") for sid in screen_ids
    }
    self_queries = [(sid, text_reps[sid]) for sid in screen_ids]
    recall5 = _recall_at_k(screen_ids, self_queries, k=5)
    record_metric(ctx.run_id, "eval_recall_at_5", recall5)
    log.info("eval recall@5=%.2f n_queries=%s", recall5, len(self_queries))

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO screens_eval (embedding_model_version, n_queries, recall_at_5)
            VALUES (%s, %s, %s)
            """,
            (SBERT_MODEL_VERSION, len(self_queries), recall5),
        )
        conn.commit()
    return {"recall_at_5": recall5, "n_queries": len(self_queries)}

"""Collect and persist pipeline health + data quality metrics."""

from __future__ import annotations

import numpy as np

from rico_pipeline.db import fetch_all, fetch_one
from rico_pipeline.logging_utils import get_logger
from rico_pipeline.run_context import RunContext, record_metric

log = get_logger(__name__)


def collect_data_quality(ctx: RunContext) -> dict:
    run_id = ctx.run_id
    meta_total = fetch_one(
        "SELECT COUNT(*) FROM screens_metadata WHERE run_id = %s", (run_id,)
    )[0]
    meta_with_payload = fetch_one(
        "SELECT COUNT(*) FROM screens_metadata WHERE run_id = %s AND extraction_payload IS NOT NULL",
        (run_id,),
    )[0]
    meta_confident = fetch_one(
        "SELECT COUNT(*) FROM screens_metadata WHERE run_id = %s AND confidence >= 0.5",
        (run_id,),
    )[0]
    review_count = fetch_one(
        "SELECT COUNT(*) FROM screens_review_queue WHERE run_id = %s", (run_id,)
    )[0]
    pct_payload = (100.0 * meta_with_payload / meta_total) if meta_total else 0.0
    pct_conf = (100.0 * meta_confident / meta_total) if meta_total else 0.0
    pct_review = (100.0 * review_count / meta_total) if meta_total else 0.0

    emb_rows = fetch_all(
        """
        SELECT model_version, embedding_kind, COUNT(*)
        FROM screens_embeddings WHERE run_id = %s
        GROUP BY model_version, embedding_kind
        """,
        (run_id,),
    )
    vectors = fetch_all(
        "SELECT embedding_kind, vector::text FROM screens_embeddings WHERE run_id = %s",
        (run_id,),
    )
    zero_count = 0
    dims: dict[str, list[int]] = {}
    for kind, vec_text in vectors:
        # pgvector text format: [0.1,0.2,...]
        arr = np.array(eval(vec_text), dtype=np.float32)
        dims.setdefault(kind, []).append(len(arr))
        if np.linalg.norm(arr) < 1e-9:
            zero_count += 1
    pct_zero = (100.0 * zero_count / len(vectors)) if vectors else 0.0

    distinct_apps = fetch_one(
        "SELECT COUNT(DISTINCT app_package) FROM screens_metadata WHERE run_id = %s",
        (run_id,),
    )[0]
    distinct_cats = fetch_one(
        "SELECT COUNT(DISTINCT category) FROM screens_metadata WHERE run_id = %s",
        (run_id,),
    )[0]

    metrics = {
        "metadata_row_count": float(meta_total),
        "metadata_pct_extraction_payload": pct_payload,
        "metadata_pct_confidence_gte_0_5": pct_conf,
        "metadata_pct_review_queue": pct_review,
        "embeddings_pct_zero_norm": pct_zero,
        "distinct_app_package": float(distinct_apps),
        "distinct_category": float(distinct_cats),
    }
    for mv, kind, cnt in emb_rows:
        metrics[f"embeddings_{kind}_{mv.replace('/', '_')}_count"] = float(cnt)
        avg_dim = sum(dims.get(kind, [0])) / max(len(dims.get(kind, [1])), 1)
        metrics[f"embeddings_{kind}_avg_dim"] = avg_dim

    for name, val in metrics.items():
        record_metric(run_id, name, val)
    return metrics


def build_summary(
    ctx: RunContext,
    status: str,
    duration_s: float,
    task_stats: dict[str, dict],
    dq: dict,
) -> str:
    lines = [
        f"status={status} duration_s={duration_s:.1f} limit={ctx.limit}",
        "— task timings —",
    ]
    for task, stats in task_stats.items():
        lines.append(
            f"  {task}: duration_s={stats.get('duration_s', 0):.1f} "
            f"in={stats.get('rows_in', '-')} out={stats.get('rows_out', '-')}"
        )
    lines.append("— data quality —")
    for k, v in sorted(dq.items()):
        lines.append(f"  {k}={v:.2f}" if isinstance(v, float) else f"  {k}={v}")
    summary = "\n".join(lines)
    record_metric(ctx.run_id, "run_summary", text=summary)
    log.info("RUN SUMMARY\n%s", summary)
    return summary

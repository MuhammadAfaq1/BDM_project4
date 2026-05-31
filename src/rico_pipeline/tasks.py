"""Airflow task entrypoints — thin wrappers around pipeline stages."""

from __future__ import annotations

import time
from typing import Any

from rico_pipeline.audit import run_audit
from rico_pipeline.embed_image import run_embed_image
from rico_pipeline.embed_text import run_embed_text
from rico_pipeline.eval_task import run_eval
from rico_pipeline.extract import run_extract
from rico_pipeline.ingest import run_ingest
from rico_pipeline.load import run_load
from rico_pipeline.logging_utils import get_logger, set_run_id
from rico_pipeline.metrics import build_summary, collect_data_quality
from rico_pipeline.parse_task import run_parse
from rico_pipeline.run_context import RunContext
from rico_pipeline.slack import notify_audit_failed, notify_finished, notify_started

log = get_logger(__name__)

# XCom keys
RUN_ID_KEY = "run_id"
TASK_STATS_KEY = "task_stats"
START_TIME_KEY = "start_time"


def _ctx_from_xcom(ti, dag_run) -> RunContext:
    run_id = ti.xcom_pull(key=RUN_ID_KEY)
    limit = int(dag_run.conf.get("limit", 5))
    trigger = getattr(dag_run, "run_type", "manual") or "manual"
    set_run_id(run_id)
    return RunContext(run_id=run_id, dag_run_id=dag_run.run_id, limit=limit, trigger_type=trigger)


def _timed(stage_fn, ctx: RunContext, ti, task_name: str) -> dict:
    t0 = time.time()
    result = stage_fn(ctx)
    result["duration_s"] = time.time() - t0
    stats = ti.xcom_pull(key=TASK_STATS_KEY) or {}
    stats[task_name] = result
    ti.xcom_push(key=TASK_STATS_KEY, value=stats)
    return result


def task_begin(**context) -> dict:
    dag_run = context["dag_run"]
    ti = context["ti"]
    limit = int(dag_run.conf.get("limit", 5))
    trigger = str(getattr(dag_run, "run_type", "manual"))
    ctx = RunContext.start(dag_run_id=dag_run.run_id, limit=limit, trigger_type=trigger)
    ti.xcom_push(key=RUN_ID_KEY, value=ctx.run_id)
    ti.xcom_push(key=START_TIME_KEY, value=time.time())
    ti.xcom_push(key=TASK_STATS_KEY, value={})
    notify_started(ctx.run_id, limit, trigger)
    return {"run_id": ctx.run_id}


def task_ingest(**context) -> dict:
    ctx = _ctx_from_xcom(context["ti"], context["dag_run"])
    return _timed(run_ingest, ctx, context["ti"], "ingest")


def task_parse(**context) -> dict:
    ctx = _ctx_from_xcom(context["ti"], context["dag_run"])
    return _timed(run_parse, ctx, context["ti"], "parse")


def task_embed_image(**context) -> dict:
    ctx = _ctx_from_xcom(context["ti"], context["dag_run"])
    return _timed(run_embed_image, ctx, context["ti"], "embed_image")


def task_embed_text(**context) -> dict:
    ctx = _ctx_from_xcom(context["ti"], context["dag_run"])
    return _timed(run_embed_text, ctx, context["ti"], "embed_text")


def task_extract(**context) -> dict:
    ctx = _ctx_from_xcom(context["ti"], context["dag_run"])
    return _timed(run_extract, ctx, context["ti"], "extract")


def task_load(**context) -> dict:
    ctx = _ctx_from_xcom(context["ti"], context["dag_run"])
    return _timed(run_load, ctx, context["ti"], "load")


def task_audit(**context) -> dict:
    ctx = _ctx_from_xcom(context["ti"], context["dag_run"])
    try:
        return _timed(run_audit, ctx, context["ti"], "audit")
    except RuntimeError as exc:
        notify_audit_failed(ctx.run_id, str(exc))
        ctx.finish("paused-by-audit")
        raise


def task_eval(**context) -> dict:
    ctx = _ctx_from_xcom(context["ti"], context["dag_run"])
    return _timed(run_eval, ctx, context["ti"], "eval")


def task_finalize(**context) -> dict:
    ti = context["ti"]
    dag_run = context["dag_run"]
    ctx = _ctx_from_xcom(ti, dag_run)
    start = ti.xcom_pull(key=START_TIME_KEY) or time.time()
    duration = time.time() - start
    task_stats = ti.xcom_pull(key=TASK_STATS_KEY) or {}
    dq = collect_data_quality(ctx)
    status = "succeeded"
    ctx.finish(status)
    summary = build_summary(ctx, status, duration, task_stats, dq)
    notify_finished(ctx.run_id, status, duration, summary)
    return {"status": status, "summary": summary}

"""
RICO Pipeline DAG — Project 4.

Flow: ingest → parse → [embed_image, embed_text, extract] → load → audit → eval → finalize
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from rico_pipeline.tasks import (
    task_audit,
    task_begin,
    task_embed_image,
    task_embed_text,
    task_eval,
    task_extract,
    task_finalize,
    task_ingest,
    task_load,
    task_parse,
)

default_args = {
    "owner": "rico",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="rico_pipeline",
    default_args=default_args,
    description="RICO multimodal pipeline with traceability, audit, and metrics",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["rico", "project4"],
    params={"limit": 5},
) as dag:
    begin = PythonOperator(task_id="begin", python_callable=task_begin)
    ingest = PythonOperator(task_id="ingest", python_callable=task_ingest)
    parse = PythonOperator(task_id="parse", python_callable=task_parse)
    embed_image = PythonOperator(task_id="embed_image", python_callable=task_embed_image)
    embed_text = PythonOperator(task_id="embed_text", python_callable=task_embed_text)
    extract = PythonOperator(task_id="extract", python_callable=task_extract)
    load = PythonOperator(task_id="load", python_callable=task_load)
    audit = PythonOperator(task_id="audit", python_callable=task_audit)
    eval_task = PythonOperator(task_id="eval", python_callable=task_eval)
    finalize = PythonOperator(task_id="finalize", python_callable=task_finalize)

    begin >> ingest >> parse >> [embed_image, embed_text, extract] >> load >> audit >> eval_task >> finalize

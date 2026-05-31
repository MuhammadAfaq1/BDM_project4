# Project 4 — RICO Pipeline (Notebook → Airflow DAG)

Production Airflow implementation of the [week07 RICO lab](../week07/) pipeline with traceability, duplicate-detection audit, observability metrics, and Slack notifications.

## Prerequisites

- Docker Desktop
- Ollama running locally with `qwen2.5:3b` (`ollama pull qwen2.5:3b`)
- Week 7 lab assets cached locally:
  - `week07/data/train-00000-of-00008.parquet` (~206 MB)
  - `week07/models/open_clip_pytorch_model.bin` (~577 MB)
  - `week07/models/sbert/` (SBERT weights)

Copy `.env.example` to `.env` and set `SLACK_WEBHOOK_URL` (optional — logs only if unset).

## Quickstart

```powershell
cd project4
copy .env.example .env
make up
```

Open **Airflow UI**: http://localhost:8099 (login `admin` / `admin`)

Trigger the DAG with config:

```json
{"limit": 5}
```

Or from CLI:

```powershell
make trigger
```

## DAG shape

```
ingest → parse → [embed_image, embed_text, extract] → load → audit → eval → finalize
```

| Task | Purpose |
|------|---------|
| `ingest` | Stream RICO screens → MinIO + `screens_metadata` |
| `parse` | View hierarchy → flat text in MinIO |
| `embed_image` | CLIP ViT-B/32 → `screens_embeddings` (image) |
| `embed_text` | SBERT → `screens_embeddings` (text) |
| `extract` | Ollama LLM → staged JSON in MinIO |
| `load` | Upsert extraction into `screens_metadata` / review queue |
| `audit` | Duplicate detection — **fails the run** if duplicates found |
| `eval` | recall@5 self-test |
| `finalize` | Persist metrics + Slack summary |

## Connection details (host)

| Service | Endpoint |
|---------|----------|
| Postgres (rico) | `localhost:5435` — `rico` / `rico` |
| Postgres (airflow) | same instance, database `airflow` |
| MinIO | http://localhost:9002 |
| Airflow | http://localhost:8099 |
| Ollama | http://localhost:11434 (via `host.docker.internal` from containers) |

## Traceability (SQL)

```sql
-- Which run produced this row?
SELECT m.screen_id, m.run_id, r.started_at, r.clip_version, r.sbert_version, r.llm_model
FROM screens_metadata m
JOIN pipeline_runs r ON r.run_id = m.run_id;

-- Metrics for a run
SELECT metric_name, metric_value, metric_text
FROM pipeline_metrics
WHERE run_id = '<uuid>'
ORDER BY metric_name;

-- Audit history
SELECT * FROM audit_results ORDER BY created_at DESC;
```

Every destination row has `run_id` + `source_fingerprint` (SHA-256 of input bytes/text).

## Idempotency

All writes use `INSERT ... ON CONFLICT DO UPDATE`. Re-triggering with `LIMIT=5` updates rows in place — **no new rows** in destination tables.

Verify:

```sql
SELECT COUNT(*) FROM screens_metadata;
-- trigger again, count should be unchanged
```

## Test the audit circuit breaker

```powershell
.\test-audit.ps1      # triggers DAG, injects duplicate after load, audit should fail
.\cleanup-audit.ps1   # remove duplicate and restore PK when done
```

The script keeps the primary key in place during embed/load (upserts need it), inserts a duplicate row after `load` succeeds, then waits for `audit` to fail. Check Airflow at http://localhost:8099 — `audit` should be red and `eval` skipped.

## Metrics explained

| Metric | Meaning |
|--------|---------|
| `metadata_pct_extraction_payload` | % of screens with LLM JSON loaded |
| `metadata_pct_confidence_gte_0_5` | % with confidence ≥ 0.5 |
| `metadata_pct_review_queue` | % routed to human review |
| `embeddings_pct_zero_norm` | % zero-norm vectors (embedder bug signal) |
| `distinct_app_package` / `distinct_category` | Sanity: diversity of ingested apps |
| `eval_recall_at_5` | Self-test recall (≈1.0 on small LIMIT) |

End-of-run summary appears in Airflow task logs for `finalize` and in `pipeline_metrics.run_summary`.

## Project layout

```
project4/
  dags/rico_pipeline_dag.py   # thin orchestration only
  src/rico_pipeline/          # business logic
  migrations/                 # Postgres schema + traceability
  prompts/extraction_v1.txt   # versioned LLM prompt
  docker-compose.yml
  Makefile
```

## Troubleshooting

**DAG import error** — ensure `src/` is mounted and `PYTHONPATH` includes `/opt/rico-pipeline/src`.

**Ollama connection refused** — Ollama must run on the host; set `OLLAMA_URL=http://host.docker.internal:11434` in `.env`.

**Missing models** — run week 7 setup first or download assets into `week07/models/` and `week07/data/`.

**Audit fails on first run** — remove manually inserted duplicates from `screens_embeddings`.

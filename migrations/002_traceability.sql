\c rico

-- Pipeline run registry
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id          UUID PRIMARY KEY,
    dag_run_id      TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running',
    limit_param     INTEGER NOT NULL,
    git_sha         TEXT,
    clip_version    TEXT NOT NULL,
    sbert_version   TEXT NOT NULL,
    llm_model       TEXT NOT NULL,
    prompt_version  TEXT NOT NULL,
    trigger_type    TEXT
);

CREATE TABLE IF NOT EXISTS audit_results (
    id          BIGSERIAL PRIMARY KEY,
    run_id      UUID NOT NULL REFERENCES pipeline_runs(run_id),
    audit_name  TEXT NOT NULL,
    passed      BOOLEAN NOT NULL,
    details     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pipeline_metrics (
    id           BIGSERIAL PRIMARY KEY,
    run_id       UUID NOT NULL REFERENCES pipeline_runs(run_id),
    metric_name  TEXT NOT NULL,
    metric_value DOUBLE PRECISION,
    metric_text  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, metric_name)
);

ALTER TABLE screens_metadata
    ADD COLUMN IF NOT EXISTS run_id UUID REFERENCES pipeline_runs(run_id),
    ADD COLUMN IF NOT EXISTS source_fingerprint TEXT;

ALTER TABLE screens_embeddings
    ADD COLUMN IF NOT EXISTS run_id UUID REFERENCES pipeline_runs(run_id),
    ADD COLUMN IF NOT EXISTS source_fingerprint TEXT;

ALTER TABLE screens_review_queue
    ADD COLUMN IF NOT EXISTS run_id UUID REFERENCES pipeline_runs(run_id),
    ADD COLUMN IF NOT EXISTS source_fingerprint TEXT;

CREATE INDEX IF NOT EXISTS idx_screens_metadata_run_id ON screens_metadata(run_id);
CREATE INDEX IF NOT EXISTS idx_screens_embeddings_run_id ON screens_embeddings(run_id);

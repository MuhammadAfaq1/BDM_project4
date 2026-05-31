# Remove test duplicate and restore primary key on screens_embeddings.
Set-Location $PSScriptRoot

Write-Host "Removing duplicate rows (keep one row per key)..."
docker compose exec postgres psql -U rico -d rico -c @"
DELETE FROM screens_embeddings a
USING screens_embeddings b
WHERE a.ctid > b.ctid
  AND a.screen_id = b.screen_id
  AND a.model_name = b.model_name
  AND a.model_version = b.model_version
  AND a.embedding_kind = b.embedding_kind;
"@

Write-Host "Restoring primary key..."
docker compose exec postgres psql -U rico -d rico -c "ALTER TABLE screens_embeddings ADD CONSTRAINT screens_embeddings_pkey PRIMARY KEY (screen_id, model_name, model_version, embedding_kind);"

Write-Host "Cleanup complete. You can trigger the DAG again for a normal successful run."

# Test the audit circuit breaker: trigger a full DAG run, inject a duplicate
# after load succeeds (embed upserts still need the PK), then verify audit fails.
Set-Location $PSScriptRoot

function Get-TaskState($runId, $taskId) {
    $lines = docker compose exec -T airflow-scheduler airflow tasks states-for-dag-run rico_pipeline $runId 2>$null
    foreach ($line in $lines) {
        if ($line -match "\|\s*$([regex]::Escape($taskId))\s*\|\s*(\S+)") {
            $state = $matches[2].Trim()
            if ($state -and $state -ne "None") { return $state }
        }
    }
    return "pending"
}

function Trigger-Dag {
    docker compose exec -T airflow-scheduler airflow dags trigger rico_pipeline 2>&1 | Out-Null
    Start-Sleep -Seconds 3
    $out = docker compose exec -T airflow-scheduler airflow dags list-runs -d rico_pipeline --no-backfill 2>$null | Out-String
    if ($out -match '(manual__\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00)') { return $matches[1] }
    throw "Could not parse run id from list-runs output."
}

# Restore PK if a previous test left the table without it
$pk = docker compose exec -T postgres psql -U rico -d rico -t -c "SELECT COUNT(*) FROM pg_constraint WHERE conrelid = 'screens_embeddings'::regclass AND contype = 'p';" 2>$null
if ($pk.Trim() -eq "0") {
    Write-Host "Restoring primary key from a previous test..."
    & "$PSScriptRoot\cleanup-audit.ps1"
}

Write-Host "Step 1: Trigger DAG..."
$runId = Trigger-Dag
Write-Host "Watching run: $runId"

Write-Host "Step 2: Wait for load to succeed, then inject duplicate before audit finishes..."
$injected = $false
$deadline = (Get-Date).AddMinutes(8)
while ((Get-Date) -lt $deadline) {
    $loadState = Get-TaskState $runId "load"
    $auditState = Get-TaskState $runId "audit"

    if ($auditState -eq "failed") {
        Write-Host "Audit already failed (duplicate may exist from a prior test)."
        $injected = $true
        break
    }

    if ($loadState -eq "success" -and $auditState -notin @("success", "failed", "skipped", "upstream_failed")) {
        Write-Host "Load succeeded. Injecting duplicate..."
        docker compose exec postgres psql -U rico -d rico -c "ALTER TABLE screens_embeddings DROP CONSTRAINT IF EXISTS screens_embeddings_pkey;" | Out-Null
        docker compose exec postgres psql -U rico -d rico -c "INSERT INTO screens_embeddings (screen_id, model_name, model_version, embedding_kind, vector, run_id, source_fingerprint) SELECT screen_id, model_name, model_version, embedding_kind, vector, run_id, source_fingerprint FROM screens_embeddings LIMIT 1;" | Out-Null
        Write-Host "Duplicate inserted."
        $injected = $true
        break
    }

    if ($auditState -eq "success") {
        throw "Audit finished before duplicate was injected. Re-run the script; the pipeline must be watched from the start."
    }

    if ($loadState -in @("failed", "upstream_failed")) {
        throw "Load failed ($loadState). Check Airflow logs at http://localhost:8099"
    }

    Start-Sleep -Seconds 5
}

if (-not $injected) {
    throw "Timed out waiting for load to succeed."
}

Write-Host "Step 3: Wait for audit to fail..."
while ((Get-Date) -lt $deadline) {
    $auditState = Get-TaskState $runId "audit"
    $evalState = Get-TaskState $runId "eval"
    if ($auditState -eq "failed") {
        Write-Host "SUCCESS: audit task failed as expected."
        Write-Host "eval task state: $evalState (should be skipped/upstream_failed)"
        Write-Host ""
        Write-Host "Open http://localhost:8099 and confirm audit is red."
        Write-Host "After testing, run: .\cleanup-audit.ps1"
        exit 0
    }
    if ($auditState -eq "success") {
        throw "Audit passed unexpectedly. Duplicate was not detected."
    }
    Start-Sleep -Seconds 5
}

Write-Host "Timed out waiting for audit. Check http://localhost:8099 for run $runId"
Write-Host "After testing, run: .\cleanup-audit.ps1"
exit 1

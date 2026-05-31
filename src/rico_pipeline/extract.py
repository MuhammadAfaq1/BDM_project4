"""LLM extraction via Ollama — stages results for load."""

from __future__ import annotations

import json

import requests

from rico_pipeline.config import OLLAMA_MODEL, OLLAMA_URL, PROMPT_PATH, PROMPT_VERSION
from rico_pipeline.logging_utils import get_logger
from rico_pipeline.minio_client import get_bytes, put_bytes
from rico_pipeline.run_context import RunContext, screen_ids_for_run, sha256_text

log = get_logger(__name__)


def _prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _extract_one(text_rep: str) -> dict:
    prompt = _prompt_template().replace("{hierarchy_text}", text_rep)
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=180,
    )
    resp.raise_for_status()
    return json.loads(resp.json()["response"])


def run_extract(ctx: RunContext) -> dict:
    screen_ids = screen_ids_for_run(ctx.run_id)
    ok = 0
    for sid in screen_ids:
        text = get_bytes(f"screens/{sid}.text.txt").decode("utf-8")
        fp = sha256_text(text)
        try:
            body = _extract_one(text)
            payload = {
                "screen_id": sid,
                "body": body,
                "prompt_version": PROMPT_VERSION,
                "confidence": float(body.get("confidence", 0)),
                "source_fingerprint": fp,
                "raw_output": None,
                "needs_review": False,
            }
            ok += 1
        except (json.JSONDecodeError, KeyError, requests.RequestException) as exc:
            log.warning("extract failed screen=%s: %s", sid, exc)
            payload = {
                "screen_id": sid,
                "body": None,
                "prompt_version": PROMPT_VERSION,
                "confidence": None,
                "source_fingerprint": fp,
                "raw_output": str(exc),
                "needs_review": True,
            }
        put_bytes(
            f"screens/{sid}.extraction.json",
            json.dumps(payload).encode("utf-8"),
            "application/json",
        )
        log.info("extract screen %s needs_review=%s", sid, payload["needs_review"])
    log.info("extract complete rows_out=%s", ok)
    return {"rows_in": len(screen_ids), "rows_out": ok}

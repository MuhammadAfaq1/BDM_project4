"""RICO production pipeline — configuration from environment."""

from __future__ import annotations

import os
from pathlib import Path

POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://rico:rico@postgres:5432/rico")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "rico-raw")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

CLIP_ARCH = "ViT-B-32"
CLIP_PRETRAINED = "laion2b_s34b_b79k"
CLIP_MODEL_VERSION = f"open-clip-{CLIP_ARCH}-{CLIP_PRETRAINED.replace('_', '-')}"
SBERT_MODEL_VERSION = "sentence-transformers/all-MiniLM-L6-v2"
PROMPT_VERSION = "v1"

PROMPT_PATH = Path(os.getenv("RICO_PROMPT_PATH", "prompts/extraction_v1.txt"))
CLIP_WEIGHTS_PATH = os.getenv("RICO_CLIP_WEIGHTS", "models/open_clip_pytorch_model.bin")
SBERT_PATH = os.getenv("RICO_SBERT_PATH", "models/sbert")
PARQUET_PATH = os.getenv("RICO_PARQUET_PATH", "data/train-00000-of-00008.parquet")

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

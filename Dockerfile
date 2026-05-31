FROM apache/airflow:2.10.4-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /opt/rico-pipeline/
COPY src /opt/rico-pipeline/src
COPY prompts /opt/rico-pipeline/prompts
RUN chown -R airflow:root /opt/rico-pipeline

USER airflow
WORKDIR /opt/rico-pipeline
RUN pip install --no-cache-dir .

ENV PYTHONPATH=/opt/rico-pipeline/src:/opt/airflow/dags
ENV RICO_PROMPT_PATH=/opt/rico-pipeline/prompts/extraction_v1.txt
ENV RICO_CLIP_WEIGHTS=/opt/rico-pipeline/models/open_clip_pytorch_model.bin
ENV RICO_SBERT_PATH=/opt/rico-pipeline/models/sbert
ENV RICO_PARQUET_PATH=/opt/rico-pipeline/data/train-00000-of-00008.parquet

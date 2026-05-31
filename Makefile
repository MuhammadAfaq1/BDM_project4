.PHONY: help up down clean logs build trigger test-audit

COMPOSE := docker compose

help:
	@echo "Project 4 — RICO Airflow Pipeline"
	@echo "  make build   build Airflow image"
	@echo "  make up      start Postgres, MinIO, Airflow"
	@echo "  make down    stop services"
	@echo "  make clean   stop and wipe volumes"
	@echo "  make logs    tail Airflow scheduler logs"
	@echo "  make trigger trigger DAG with LIMIT=5"

build:
	$(COMPOSE) build airflow-webserver airflow-scheduler airflow-init

up: build
	$(COMPOSE) up -d --wait postgres minio
	$(COMPOSE) up -d minio-init
	$(COMPOSE) run --rm airflow-init
	$(COMPOSE) up -d airflow-webserver airflow-scheduler
	@echo "Airflow UI: http://localhost:8099  (admin / admin)"

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f --tail=100 airflow-scheduler

trigger:
	$(COMPOSE) exec airflow-scheduler airflow dags trigger rico_pipeline --conf '{"limit": 5}'

test-audit:
	@echo "On Windows run: .\\test-audit.ps1"

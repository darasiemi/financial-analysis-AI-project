# Load local environment variables
ifneq (,$(wildcard .env))
include .env
export
endif

# db_start:
# 	cd ingestion && docker compose --env-file ../.env up -d

db_stop:
	cd ingestion && docker compose down

psql:
	cd ingestion && \
	set -a && . ../.env && set +a && \
	docker compose --env-file ../.env exec postgres psql \
		-U $$POSTGRES_USER \
		-d $$POSTGRES_DB
scrape:
	uv run python -u -m ingestion.pipelines.ingest_reports

chunks:
	uv run python -u -m ingestion.pipelines.load_report_chunks

tables:
	uv run python -u -m ingestion.pipelines.load_report_tables

ingest: chunks tables

check_json_table:
	uv run python -m scripts.view_table

notebook:
	uv run jupyter-notebook

build_index:
	uv run python -u -m retrieval.index

test_text_search:
	uv run python -m scripts.search \
		"What was GTCO's profit before tax in 2023?" \
		--mode keyword \
		--ticker GTCO \
		--year 2023

test_vector_search:
	uv run python -m scripts.search \
		"What was GTCO's profit before tax in 2023?" \
		--mode vector \
		--ticker GTCO \
		--year 2023

test_hybrid_search:
	uv run python -m scripts.search \
		"What was GTCO's profit before tax in 2023?" \
		--mode hybrid \
		--ticker GTCO \
		--year 2023

test_rag:
	uv run python -m scripts.rag_qa \
		"$(or $(QUERY),Who is the Group Chief Executive Officer?)" \
		--mode $(or $(MODE),hybrid) \
		--top-k $(or $(TOP_K),20) \
		$(if $(TICKER),--ticker $(TICKER),) \
		$(if $(YEAR),--year $(YEAR),) \
		--show-context

test_agent:
	uv run python -m scripts.agent_qa \
		"$(or $(QUERY),Who is the Group Chief Executive Officer?)" \
		--top-k $(or $(TOP_K),8) \
		$(if $(TICKER),--ticker $(TICKER),) \
		$(if $(YEAR),--year $(YEAR),) \
		$(if $(SHOW_CONTEXT),--show-context,) \
		$(if $(SHOW_RAW_TOOLS),--show-raw-tools,)

generate_eval:
	uv run python -m scripts.generate_eval_data \
		--n $(or $(N),100) \
		--output $(or $(DATASET),data/evaluation/benchmark.jsonl) \
		--seed $(or $(SEED),42) \
		--pool-size $(or $(POOL_SIZE),2000) \
		--minimum-quality $(or $(MIN_QUALITY),0.90) \
		--minimum-difficulty $(or $(MIN_DIFFICULTY),0.80) \
		--minimum-financial-relevance $(or $(MIN_FINANCIAL),0.90)

eval_rag:
	uv run python -m scripts.evaluate \
		--pipeline rag \
		--dataset $(or $(DATASET),data/evaluation/benchmark.jsonl) \
		--mode $(or $(MODE),hybrid) \
		--top-k $(or $(TOP_K),8) \
		$(if $(LIMIT),--limit $(LIMIT),)

eval_agent:
	uv run python -m scripts.evaluate \
		--pipeline agent \
		--dataset $(or $(DATASET),data/evaluation/benchmark.jsonl) \
		--top-k $(or $(TOP_K),8) \
		$(if $(LIMIT),--limit $(LIMIT),)

.PHONY: app postgres monitoring backend frontend investor_snapshot stop_app


postgres:
	docker compose up -d postgres


monitoring:
	docker compose up -d grafana


investor_snapshot:
	uv run python -m scripts.build_investor_snapshot


backend:
	uv run --group backend uvicorn deployment.backend.main:app \
		--host 0.0.0.0 \
		--port 8000 \
		--reload \
		--reload-dir deployment \
		--reload-dir agent \
		--reload-dir rag \
		--reload-dir retrieval \
		--reload-dir ingestion \
		--reload-dir monitoring \
		
test_backend:
	curl -X POST http://localhost:8000/api/v1/query \
		-H "Content-Type: application/json" \
		-d '{ \
			"question": "What was GTCO'\''s profit before tax in 2025?", \
			"session_id": "'$$(uuidgen)'", \
			"pipeline": "rag", \
			"retrieval_mode": "hybrid", \
			"top_k": 8, \
			"ticker": null, \
			"report_year": null, \
			"model": "gemini-2.5-flash" \
		}'

frontend:
	uv run --group frontend streamlit run deployment/frontend/app.py


app:
	$(MAKE) postgres
	$(MAKE) monitoring
	$(MAKE) investor_snapshot
	@trap 'kill 0' INT TERM EXIT; \
	$(MAKE) backend & \
	$(MAKE) frontend & \
	wait


stop_app:
	docker compose down

synthetic_test:
	uv run python scripts/synthetic_traffic.py \
		--requests $(REQUESTS) \
		--delay 3 \
		--pipeline mixed

test_fast:
	uv run --group test pytest \
		tests/smoke \
		tests/integration \
		-v

format:
	uv run --group quality isort .
	uv run --group quality black .


format_check:
	uv run --group quality isort --check-only .
	uv run --group quality black --check .


lint:
	uv run --group quality pylint \
		agent \
		deployment \
		ingestion \
		monitoring \
		rag \
		retrieval \
		scripts


quality:
	$(MAKE) format_check
	$(MAKE) lint


precommit:
	uv run --group quality pre-commit run --all-files

# ---------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------

RAILWAY_DB_SERVICE ?= Postgres
RAILWAY_TUNNEL_PORT ?= 55432

LOCAL_POSTGRES_HOST ?= $(POSTGRES_HOST)
LOCAL_POSTGRES_PORT ?= $(POSTGRES_PORT)
LOCAL_POSTGRES_DB ?= $(POSTGRES_DB)
LOCAL_POSTGRES_USER ?= $(POSTGRES_USER)

PG18_BIN := $(shell brew --prefix postgresql@18)/bin

# ---------------------------------------------------------------------
# Railway database
# ---------------------------------------------------------------------


.PHONY: railway-tunnel sync-monitoring-from-railway


railway-tunnel:
	@echo "Opening SSH tunnel to Railway PostgreSQL..."
	railway connect $(RAILWAY_DB_SERVICE) \
		--tunnel-only \
		--port $(RAILWAY_TUNNEL_PORT)


sync-monitoring-from-railway:
	@if [ -z "$(RAILWAY_POSTGRES_PASSWORD)" ]; then \
		echo "Error: RAILWAY_POSTGRES_PASSWORD is not set."; \
		exit 1; \
	fi

	@if [ -z "$(POSTGRES_PASSWORD)" ]; then \
		echo "Error: POSTGRES_PASSWORD is not set."; \
		exit 1; \
	fi

	@echo "Dumping Railway monitoring data..."

	@PGPASSWORD="$(RAILWAY_POSTGRES_PASSWORD)" \
	$(PG18_BIN)/pg_dump \
		-h 127.0.0.1 \
		-p $(RAILWAY_TUNNEL_PORT) \
		-U postgres \
		-d railway \
		--schema=monitoring \
		--data-only \
		--format=custom \
		--no-owner \
		--no-privileges \
		--file=/tmp/railway_monitoring.dump

	@echo "Clearing local monitoring data..."

	@PGPASSWORD="$(POSTGRES_PASSWORD)" \
	psql \
		-h $(LOCAL_POSTGRES_HOST) \
		-p $(LOCAL_POSTGRES_PORT) \
		-U $(LOCAL_POSTGRES_USER) \
		-d $(LOCAL_POSTGRES_DB) \
		-c "TRUNCATE monitoring.feedback, monitoring.llm_calls, monitoring.interactions, monitoring.sessions RESTART IDENTITY CASCADE;"

	@echo "Restoring Railway monitoring data locally..."

	@PGPASSWORD="$(POSTGRES_PASSWORD)" \
	$(PG18_BIN)/pg_restore \
		-h $(LOCAL_POSTGRES_HOST) \
		-p $(LOCAL_POSTGRES_PORT) \
		-U $(LOCAL_POSTGRES_USER) \
		-d $(LOCAL_POSTGRES_DB) \
		--data-only \
		--no-owner \
		--no-privileges \
		/tmp/railway_monitoring.dump

	@rm -f /tmp/railway_monitoring.dump

	@echo "Monitoring data synced successfully."
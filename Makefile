db_start:
	cd ingestion && docker compose --env-file ../.env up -d

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

.PHONY: app postgres monitoring backend frontend stop_app


postgres:
	docker compose up -d postgres


monitoring:
	docker compose up -d grafana


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
		--env-file .env


frontend:
	uv run --group frontend streamlit run deployment/frontend/app.py


app:
	$(MAKE) postgres
	$(MAKE) monitoring
	@trap 'kill 0' INT TERM EXIT; \
	$(MAKE) backend & \
	$(MAKE) frontend & \
	wait


stop_app:
	docker compose down
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
db:
	cd ingestion && docker compose up -d

logs:
	cd ingestion && docker compose logs -f postgres

psql:
	cd ingestion && docker compose exec postgres psql \
		-U $(POSTGRES_USER) \
		-d $(POSTGRES_DB)
scrape:
	uv run python -u -m ingestion.pipelines.ingest_reports

chunks:
	uv run python -u -m ingestion.pipelines.load_report_chunks

tables:
	uv run python -u -m ingestion.pipelines.load_report_tables

ingest: chunks tables

check_json_table:
	uv run python -m scripts.view_table
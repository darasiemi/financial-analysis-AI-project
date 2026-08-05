# Implementation setup

## Data Ingestion
Go to the ingestion directory
```bash
cd ingestion
```
To scrape the data
```bash
uv add requests playwright
uv run playwright install chromium
```
Run the script
```bash
uv run python download_annual_reports.py
```

To install things for dlt
```bash
uv add pymupdf python-dotenv
```
To run dlt ingestion to database
First go to the dlt directory
```bash
cd dlt
```
```bash
uv run python ingest_reports.py
```
Also start postgres database
```bash
docker compose up -d
```
After ingestion, check that the the data is in the database
```bash
docker compose exec postgres psql \
  -U financial_user \
  -d financial_analysis
```
Next ingestion step
report_pages
→ clean repeated headers and footers
→ create report_chunks
→ load chunks into PostgreSQL
→ generate embeddings
→ store vectors with pgvector

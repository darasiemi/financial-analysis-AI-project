# Implementation setup

## Data Ingestion
Create data directory
```bash
mkdir data
```
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
uv add pymupdf python-dotenv psycopg2-binary "dlt[postgres]"
```
To run dlt ingestion to database
First go to the dlt directory
```bash
cd pipelines
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
Now run the dlt pipeline to processing such as chunk, remove duplicates, remove whitespaces, separate tables from text etc.
```bash
uv run python -m ingestion.pipelines.load_report_chunks
```
Run the docker command to run psql on the database again and inspect the chunk type
```bash
SELECT
    ticker,
    report_year,
    content_type,
    COUNT(*) AS chunk_count,
    ROUND(AVG(word_count), 0) AS average_words
FROM financial_analysis.report_chunks
GROUP BY ticker, report_year, content_type
ORDER BY ticker, report_year, content_type;
```

Run a quick quality check by sampling chunks
```bash
SELECT
    ticker,
    report_year,
    section_title,
    pdf_page_start,
    pdf_page_end,
    word_count,
    LEFT(text, 1200) AS preview
FROM financial_analysis.report_chunks
ORDER BY RANDOM()
LIMIT 20;
```
Check that 
Next ingestion step
report_pages
→ clean repeated headers and footers
→ create report_chunks
→ load chunks into PostgreSQL
→ generate embeddings
→ store vectors with pgvector

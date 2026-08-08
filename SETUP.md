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
Install dependencies (assumes `uv` already instead)
```bash
uv add requests playwright pymupdf python-dotenv psycopg2-binary "dlt[postgres]" psycopg tabulate jupyter google-genai
uv run playwright install chromium
```
More dependencies installation for bvector database
```bash
uv add sentence-transformers pgvector
```

Run the script
```bash
uv run python download_annual_reports.py
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

To extract the tables for structured financial data extraction
```bash
uv run python -m ingestion.pipelines.load_report_tables
```
To view the json "table", run
```bash
uv run python -m scripts.view_table
```
To check the narration
```bash
SELECT
    chunk_id,
    pdf_page_start,
    pdf_page_end,
    section_title,
    text
FROM financial_analysis.report_chunks
WHERE ticker = 'GTCO'
  AND text ILIKE '%Statutory Audit Committee%';
```
## Automated Makefile Commands for Ingestion (Recommended)

The project includes a `Makefile` to simplify common development and ingestion tasks.

Run all commands from the project root directory.

### Start PostgreSQL

```bash
make db
```

Starts the PostgreSQL Docker container in detached mode using the Docker Compose configuration in `ingestion/docker-compose.yml`.

---

### View PostgreSQL logs

```bash
make logs
```

Streams the PostgreSQL container logs in real time.

Press `Ctrl + C` to stop following the logs (the database container will continue running).

---

### Open a PostgreSQL shell

```bash
make psql
```

Opens an interactive `psql` session inside the PostgreSQL Docker container using the configured `POSTGRES_USER` and `POSTGRES_DB` environment variables.

Exit the shell with:

```text
\q
```

---

### Scrape annual reports

```bash
make scrape
```

Downloads and ingests the configured annual reports into the database.

This should typically be run only when adding new reports or refreshing the source data.

---

### Generate narrative chunks

```bash
make chunks
```

Processes all annual reports into cleaned, paragraph-aware narrative chunks and stores them in:

```text
financial_analysis.report_chunks
```

The chunking pipeline:

- reconstructs reading order
- preserves paragraphs and section headings
- supports multi-column layouts
- excludes detected table regions from the narrative corpus

---

### Extract structured tables

```bash
make tables
```

Extracts tables directly from the source PDFs and stores them in:

```text
financial_analysis.report_tables
```

Each extracted table includes:

- table metadata
- page information
- JSON representation of the table
- a text representation for semantic retrieval

---

### Run the complete ingestion pipeline

```bash
make ingest
```

Runs both:

```bash
make chunks
make tables
```

This regenerates both the narrative and structured-table datasets from the already ingested PDF reports.

---

### Inspect an extracted table

```bash
make check_json_table
```

Displays a human-readable version of an extracted table stored in the database.

Useful for validating table extraction during development.
Check that 
Next ingestion step
report_pages
→ clean repeated headers and footers
→ create report_chunks
→ load chunks into PostgreSQL
→ generate embeddings
→ store vectors with pgvector

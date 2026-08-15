# Implementation setup

## Data Ingestion
Create data directory

Set environment variables
```bash
set -a
source .env
set +a
```
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
More depencies for the agent and evaluation
```bash
uv add python-pptx openpyxl
```
Install dependencies for deployment
```bash
uv add streamlit plotly pandas
```
Note that during deployment, I separated development and deployment dependencies. This was edited directly on my `pyproject.loml`, removing the old lock `rm uv.lock` and running the lock again `uv lock`.

For normal local development, a plain `uv sync` includes the `dev` group.

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
docker compose up -d postgres
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

### Build the Retrieval Index

After ingesting the reports, build the unified retrieval index containing both narrative chunks and extracted tables.

```bash
make build_index
```

This command:

- Loads narrative chunks from `report_chunks`.
- Loads table representations (`rag_text`) from `report_tables`.
- Generates dense embeddings for all retrieval documents.
- Stores the embeddings in PostgreSQL using `pgvector`.
- Creates the keyword (Full-Text Search) and vector indexes used during retrieval.

---

### Search the Retrieval Index

Test the retrieval system without using an LLM.

#### Keyword Search

```bash
make search \
    QUERY="What was GTCO's profit before tax in 2023?" \
    MODE=keyword \
    TICKER=GTCO \
    YEAR=2023
```

#### Vector Search

```bash
make search \
    QUERY="What was GTCO's profit before tax in 2023?" \
    MODE=vector \
    TICKER=GTCO \
    YEAR=2023
```

#### Hybrid Search

```bash
make search \
    QUERY="What was GTCO's profit before tax in 2023?" \
    MODE=hybrid \
    TICKER=GTCO \
    YEAR=2023
```

Arguments:

- `QUERY` – User question.
- `MODE` – Retrieval strategy (`keyword`, `vector`, or `hybrid`).
- `TICKER` *(optional)* – Restrict search to a specific company.
- `YEAR` *(optional)* – Restrict search to a specific reporting year.

The command returns the ranked retrieval results together with retrieval latency.

---

### Test the RAG Pipeline

Run an end-to-end Retrieval-Augmented Generation (RAG) pipeline using the selected retrieval strategy and Gemini for answer generation.

```bash
make test_rag
```

By default, this runs the question:

> Who is the Group Chief Executive Officer?

using keyword retrieval (or the configured default mode) and prints both the retrieved context and the generated answer.

To ask a different question:

```bash
make test_rag \
    QUERY="What was GTCO's profit before tax in 2023?"
```

Use a different retrieval strategy:

```bash
make test_rag \
    QUERY="What was GTCO's profit before tax in 2023?" \
    MODE=hybrid
```

Restrict retrieval to a company and reporting year:

```bash
make test_rag \
    QUERY="What was GTCO's profit before tax in 2023?" \
    MODE=hybrid \
    TICKER=GTCO \
    YEAR=2023
```

Retrieve more documents for inspection:

```bash
make test_rag \
    QUERY="Who is the Group Chief Executive Officer of Zenith?" \
    MODE=hybrid \
    TOP_K=20 \
```

Arguments:

- `QUERY` – Question to answer.
- `MODE` – Retrieval strategy (`keyword`, `vector`, or `hybrid`).
- `TOP_K` *(optional)* – Number of retrieved documents passed to the RAG pipeline.
- `TICKER` *(optional)* – Restrict retrieval to a specific company.
- `YEAR` *(optional)* – Restrict retrieval to a specific reporting year.

The command displays:

- Retrieved context from the search engine.
- The generated answer.
- End-to-end RAG execution time.


## Running the Agent

Provide any question using the `QUERY` variable.

```bash
make test_agent \
    QUERY="What was GTCO's profit before tax in 2023?"
```

---

## Restrict Search to a Company

Limit the initial retrieval to a particular company.

```bash
make test_agent \
    QUERY="Who is the Group Chief Executive Officer?" \
    TICKER=GTCO
```

---

## Restrict Search to a Reporting Year

Limit the initial retrieval to a specific annual report.

```bash
make test_agent \
    QUERY="Who is the Group Chief Executive Officer?" \
    TICKER=GTCO \
    YEAR=2023
```

---

## Change Initial Retrieval Size

Specify the number of documents retrieved during the initial hybrid search.

```bash
make test_agent \
    QUERY="Who is the Group Chief Executive Officer?" \
    TOP_K=12
```

---

## View Initial Retrieved Context

To inspect the evidence retrieved before the agent begins reasoning,

```bash
make test_agent \
    QUERY="Who is the Group Chief Executive Officer?" \
    SHOW_CONTEXT=1
```

This prints the initial narrative chunks and table representations supplied to Gemini before any additional tool calls.

---

## Example Questions

Retrieve information from annual reports

```bash
make test_agent \
    QUERY="Who is the Group Chief Executive Officer?"
```

Compare financial performance

```bash
make test_agent \
    QUERY="Compare GTCO's profit before tax in 2023 and 2024 and calculate the percentage increase."
```

Combine annual reports with current public information

```bash
make test_agent \
    QUERY="Compare GTCO's 2024 annual report with its latest publicly reported financial performance."
```
Make agent to create presentation

```bash
make test_agent \
QUERY="Create a PowerPoint presentation comparing GTCO's profit before tax in 2023 and 2024, calculate the percentage increase, and save the presentation."
```

---

## Project Structure

```
agent/
├── __init__.py
├── context.py
├── gemini.py
├── pipeline.py
└── tools/
    ├── __init__.py
    ├── calculator.py
    ├── retrieval.py
    ├── tables.py
    └── web_search.py
```

The modular design separates orchestration, LLM interaction and tool implementations, making it straightforward to add new tools or replace existing ones without modifying the overall agent pipeline.

## Evaluation 


### Generate the Benchmark

Generate the default benchmark:

```bash
make generate_eval
```

Generate a benchmark with a specific number of questions:

```bash
make generate_eval N=100
```

A stricter configuration can be used with:

```bash
make generate_eval \
	N=100 \
	POOL_SIZE=2000 \
	MIN_QUALITY=0.90 \
	MIN_DIFFICULTY=0.80 \
	MIN_FINANCIAL=0.90
```

The generated benchmark is saved to:

```text
data/evaluation/benchmark.jsonl
```

---

### Evaluate RAG

Evaluate hybrid retrieval:

```bash
make eval_rag MODE=hybrid
```

Evaluate keyword retrieval:

```bash
make eval_rag MODE=keyword
```

Evaluate semantic/vector retrieval:

```bash
make eval_rag MODE=vector
```

Run against only a subset of the benchmark:

```bash
make eval_rag MODE=hybrid LIMIT=10
```

---

### Evaluate the Agent

Evaluate the agent pipeline:

```bash
make eval_agent
```

Run a smaller agent evaluation:

```bash
make eval_agent LIMIT=10
```

---

## Streamlit app
Create config
```bash
mkdir -p .streamlit
touch .streamlit/config.toml
```
To start app container
```bash
docker compose up --build
```
Then start app
```bash
docker compose up
```
If you want to start database separately and then run streamlit
```bash
make postgres
```

## Running the Application

The application consists of three services:

- **PostgreSQL + pgvector** — database and vector store
- **FastAPI** — backend API for the RAG and agent pipelines
- **Streamlit** — frontend user interface

For local development, PostgreSQL runs in Docker, while FastAPI and Streamlit run locally using `uv`.

### Run the Complete Application

From the project root, run:

```bash
make app
```

This starts all three components:

```text
make app
   │
   ├── PostgreSQL + pgvector
   │      Docker
   │      localhost:5433
   │
   ├── FastAPI backend
   │      localhost:8000
   │
   └── Streamlit frontend
          localhost:8501
```

Once the application is running:

- **Streamlit UI:** `http://localhost:8501`
- **FastAPI:** `http://localhost:8000`
- **FastAPI API documentation:** `http://localhost:8000/docs`

Press `Ctrl+C` to stop the locally running FastAPI and Streamlit processes.

PostgreSQL runs as a detached Docker container and may continue running after `Ctrl+C`.

---

### Run Individual Services

Each service can also be started independently. This is useful for development and troubleshooting.

#### PostgreSQL

```bash
make postgres
```

Check its status:

```bash
docker compose ps postgres
```

View recent PostgreSQL logs:

```bash
docker compose logs --tail=100 postgres
```

Follow the logs continuously:

```bash
docker compose logs -f postgres
```

#### FastAPI Backend

```bash
make backend
```

The backend will be available at:

```text
http://localhost:8000
```

Interactive API documentation is available at:

```text
http://localhost:8000/docs
```

The development server uses Uvicorn's automatic reload functionality, so relevant source-code changes restart the backend automatically.

#### Streamlit Frontend

In a separate terminal, run:

```bash
make frontend
```

The frontend will be available at:

```text
http://localhost:8501
```

The Streamlit frontend communicates with the FastAPI backend over HTTP. It does not directly execute the RAG/agent pipeline or query PostgreSQL.

---

### Local Development Architecture

When using:

```bash
make app
```

the application runs as:

```text
Browser
   │
   ▼
Streamlit
localhost:8501
   │
   │ HTTP
   ▼
FastAPI
localhost:8000
   │
   │ Database connection
   ▼
PostgreSQL + pgvector
Docker
localhost:5433
```

The responsibilities are separated as follows:

- **Streamlit** handles presentation and user interaction.
- **FastAPI** exposes the backend API and runs the RAG and agent pipelines.
- **PostgreSQL/pgvector** stores the indexed financial-report content and embeddings.

---

### Stop the Application

Press:

```text
Ctrl+C
```

in the terminal running `make app` to stop FastAPI and Streamlit.

To stop the Docker services:

```bash
make stop
```

This runs `docker compose down` and does not delete the persistent PostgreSQL volume.

---

### Troubleshooting

If `make app` does not start successfully, test each component individually.

First, start PostgreSQL:

```bash
make postgres
```

Confirm that it is running:

```bash
docker compose ps postgres
```

If PostgreSQL is not healthy, inspect its logs:

```bash
docker compose logs --tail=100 postgres
```

Next, start the backend:

```bash
make backend
```

Confirm that FastAPI is available by opening:

```text
http://localhost:8000/docs
```

Finally, open another terminal and start the frontend:

```bash
make frontend
```

Then open:

```text
http://localhost:8501
```

Running the services individually makes it easier to determine whether a startup problem originates from PostgreSQL, FastAPI, or Streamlit.

---

## Running with Docker Compose

The complete application can alternatively be run inside Docker:

```bash
docker compose up --build
```

In this mode, all three services run in separate containers:

```text
Browser
   │
   ▼
Streamlit container
   │
   ▼
FastAPI container
   │
   ▼
PostgreSQL container
```

To inspect the running services:

```bash
docker compose ps
```

To view logs from all services:

```bash
docker compose logs -f
```

Or inspect an individual service:

```bash
docker compose logs -f postgres
docker compose logs -f backend
docker compose logs -f frontend
```

To stop the complete Docker Compose stack:

```bash
docker compose down
```

## Monitoring: Grafana SQL Panels

Grafana uses the provisioned PostgreSQL datasource to visualise application monitoring data. The SQL queries below power the dashboard panels for response volume, latency, application and judge costs, answer relevance, and user feedback. These panels do not need to be created manually because their queries are already defined in the version-controlled Grafana dashboard JSON and are loaded automatically when Grafana starts.

### Total Responses

```sql
SELECT
    COUNT(*) AS responses
FROM monitoring.interactions
WHERE $__timeFilter(created_at);
```

### Average Latency

```sql
SELECT
    AVG(total_latency_seconds) AS avg_latency_seconds
FROM monitoring.interactions
WHERE $__timeFilter(created_at)
  AND status = 'completed';
```

### Application Cost

```sql
SELECT
    COALESCE(
        SUM(application_cost_usd),
        0
    ) AS application_cost_usd
FROM monitoring.interactions
WHERE $__timeFilter(created_at);
```

### Judge Cost

The judge cost is tracked separately from the main application cost.

```sql
SELECT
    COALESCE(
        SUM(judge_cost_usd),
        0
    ) AS judge_cost_usd
FROM monitoring.interactions
WHERE $__timeFilter(created_at);
```

### Average Answer Relevance

```sql
SELECT
    AVG(relevance_score) AS avg_relevance
FROM monitoring.interactions
WHERE $__timeFilter(created_at)
  AND relevance_score IS NOT NULL;
```

### Thumbs-Up Rate

```sql
SELECT
    COALESCE(
        100.0
        * SUM(
            CASE
                WHEN f.rating = 1 THEN 1
                ELSE 0
            END
        )
        / NULLIF(
            COUNT(*),
            0
        ),
        0
    ) AS thumbs_up_percent
FROM monitoring.feedback f
JOIN monitoring.interactions i
    ON i.response_id = f.response_id
WHERE $__timeFilter(i.created_at);
```

### Response Volume Over Time

```sql
SELECT
    $__timeGroupAlias(
        created_at,
        '5m'
    ),
    COUNT(*) AS responses
FROM monitoring.interactions
WHERE $__timeFilter(created_at)
GROUP BY 1
ORDER BY 1;
```

### Latency Over Time

```sql
SELECT
    $__timeGroupAlias(
        created_at,
        '5m'
    ),
    AVG(
        total_latency_seconds
    ) AS latency
FROM monitoring.interactions
WHERE $__timeFilter(created_at)
  AND status = 'completed'
GROUP BY 1
ORDER BY 1;
```

### Application vs. Judge Cost

```sql
SELECT
    $__timeGroupAlias(
        created_at,
        '1h'
    ),
    SUM(
        application_cost_usd
    ) AS application_cost,
    SUM(
        judge_cost_usd
    ) AS judge_cost
FROM monitoring.interactions
WHERE $__timeFilter(created_at)
GROUP BY 1
ORDER BY 1;
```

### Agent vs. RAG Latency

```sql
SELECT
    pipeline,
    AVG(
        total_latency_seconds
    ) AS avg_latency
FROM monitoring.interactions
WHERE $__timeFilter(created_at)
  AND status = 'completed'
GROUP BY pipeline
ORDER BY pipeline;
```

### User Feedback by Pipeline

```sql
SELECT
    i.pipeline,
    COUNT(*) FILTER (
        WHERE f.rating = 1
    ) AS thumbs_up,
    COUNT(*) FILTER (
        WHERE f.rating = -1
    ) AS thumbs_down
FROM monitoring.interactions i
JOIN monitoring.feedback f
    ON f.response_id = i.response_id
WHERE $__timeFilter(i.created_at)
GROUP BY i.pipeline
ORDER BY i.pipeline;
```
In case the relevance scores are not computed, run the psql `make psql` and the run this SQL.
```bash
SELECT
    created_at,
    response_id,
    pipeline,
    relevance_score,
    judge_status,
    judge_model,
    judge_latency_seconds
FROM monitoring.interactions
ORDER BY created_at DESC
LIMIT 20;
```

### Dashboard Provisioning

The Grafana dashboard is stored in:

```text
monitoring/grafana/dashboards/financial-analysis-monitoring.json
```

The dashboard provider is configured in:

```text
monitoring/grafana/provisioning/dashboards/dashboards.yml
```

and the PostgreSQL datasource is configured in:

```text
monitoring/grafana/provisioning/datasources/datasource.yml
```

These files are mounted into the Grafana container through Docker Compose. As a result, the monitoring dashboard and its SQL panels are provisioned automatically when Grafana starts, making the monitoring setup reproducible without requiring the panels to be configured manually through the Grafana UI.

The grafana can be viewed locally in
`http://localhost:3000`

To send some synthetic payloads
```bash
make synthetic_test REQUESTS=20
```

```bash
uv add --group quality black isort pylint pre-commit
```
```bash
uv add --group test pytest httpx
```
To install the git hook
```bash
uv run --group quality pre-commit install
```

Test everything once
```bash
uv run --group quality pre-commit run --all-files
```

To make `check_streamlit.sh` executable
Run
```bash
chmod +x scripts/check_streamlit.sh
```

### Run Fast Integration Tests

Run the smoke and integration test suite:

```bash
make test_fast
```

This target executes:

```bash
uv run --group test pytest \
    tests/smoke \
    tests/integration \
    -v
```

The test suite includes:

- **Import checks** — verifies that the main application modules can be imported successfully.
- **PostgreSQL connectivity** — verifies that the application can connect to the PostgreSQL database.
- **Monitoring schema creation** — verifies that the monitoring database schema can be created successfully.
- **FastAPI startup** — verifies that the FastAPI application starts without errors.
- **RAG integration test** — sends a mocked RAG request through the FastAPI endpoint and verifies that a valid response is returned.
- **Agent integration test** — sends a mocked Agent request through the FastAPI endpoint and verifies that a valid response is returned.

The RAG and Agent calls are mocked so that the fast integration tests do not make real LLM API calls. This keeps the test suite fast, deterministic, and suitable for running on every push and pull request.

To run the tests:

```bash
make test_fast
```

A successful run should report all tests as passed:

```text
tests/smoke/...
tests/integration/...

================= passed =================
```

## Code Quality and Testing

The project provides Makefile targets for code formatting, linting, pre-commit checks, and automated testing.

### Format Code

Automatically format Python code with Black and sort imports with isort:

```bash
make format
```

### Check Formatting

Check whether the code follows Black formatting and isort import-ordering rules without modifying any files:

```bash
make format_check
```

### Run Linting

Run Pylint to check the codebase for code-quality issues:

```bash
make lint
```

### Run All Code Quality Checks

Run formatting, import-ordering, and Pylint checks together:

```bash
make quality
```

### Run Pre-commit Checks

Run all configured pre-commit hooks across the repository:

```bash
make precommit
```

Once the pre-commit hooks are installed, they also run automatically when committing changes.

### Run Fast Tests

Run the smoke and integration test suite:

```bash
make test_fast
```

The fast test suite checks:

- Python module imports
- PostgreSQL connectivity
- Monitoring schema creation
- FastAPI startup
- Mocked RAG requests
- Mocked Agent requests

### Recommended Development Workflow

Before committing changes, format the code and run the quality and test suites:

```bash
make format
make quality
make test_fast
```

Then commit and push the changes:

```bash
git add .
git commit -m "Your commit message"
git push
```

GitHub Actions automatically runs the configured code-quality and integration checks on pushes and pull requests.
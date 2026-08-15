# Setup Guide

This guide explains how to install, configure, run, test, evaluate, and monitor the Financial Analysis AI project.

For system architecture, see `SYSTEM.md`.

> Run all `make` commands from the project root unless stated otherwise.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Install Dependencies](#2-install-dependencies)
3. [Configure Environment Variables](#3-configure-environment-variables)
4. [Start the Local Database](#4-start-the-local-database)
5. [Ingest and Index Annual Reports](#5-ingest-and-index-annual-reports)
6. [Test Retrieval, RAG, and Agent Pipelines](#6-test-retrieval-rag-and-agent-pipelines)
7. [Run the Application](#7-run-the-application)
8. [Evaluation](#8-evaluation)
9. [Testing and Code Quality](#9-testing-and-code-quality)
10. [Local Monitoring](#10-local-monitoring)
11. [Railway Deployment](#11-railway-deployment)
12. [Sync Production Monitoring Data Locally](#12-sync-production-monitoring-data-locally)
13. [Common Development Workflow](#13-common-development-workflow)
14. [Makefile Command Reference](#14-makefile-command-reference)

---

## 1. Prerequisites

Install:

- Python 3.11+
- `uv`
- Docker and Docker Compose
- GNU Make
- Git

Optional tools:

- Railway CLI — required only for Railway database access
- PostgreSQL 18 client tools — required only for syncing monitoring data from Railway
- Homebrew — currently required by the Makefile's PostgreSQL 18 lookup on macOS

Verify the main tools:

```bash
python --version
uv --version
docker --version
docker compose version
make --version
```

---

## 2. Install Dependencies

Install the dependencies defined in `pyproject.toml` and `uv.lock`:

```bash
uv sync
```

The Makefile uses optional dependency groups for some tasks. Install them when needed:

```bash
# Backend
uv sync --group backend

# Frontend
uv sync --group frontend

# Tests
uv sync --group test

# Code quality
uv sync --group quality
```

Install Chromium for report sources that require Playwright:

```bash
uv run playwright install chromium
```

Do not install project packages individually with `uv add` during normal setup; dependency versions should come from the committed project configuration.

---

## 3. Configure Environment Variables

Create a `.env` file in the project root with the database, Gemini, and other credentials required by the application.

The Makefile automatically loads `.env` when it exists.

At minimum, local PostgreSQL commands expect:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=financial_analysis
POSTGRES_USER=financial_user
POSTGRES_PASSWORD=<password>
```

Add the Gemini/API configuration required by the application to the same file.

Never commit `.env`. Verify that Git ignores it:

```bash
git check-ignore .env
```

---

## 4. Start the Local Database

There are two PostgreSQL targets because the repository uses Docker Compose in different contexts.

For the main local application stack:

```bash
make postgres
```

<!-- For ingestion-specific database startup using `ingestion/docker-compose.yml`:

```bash
make db_start
``` -->

Open the ingestion PostgreSQL shell with:

```bash
make psql
```
<!-- 
Stop the ingestion stack with:

```bash
make db_stop
``` -->

For the main root Docker Compose stack, use:

```bash
make stop_app
```

> `stop_app` runs `docker compose down`. It does not remove persistent volumes unless Docker Compose is explicitly invoked with `-v`.

---

## 5. Ingest and Index Annual Reports

### 5.1 Download reports

```bash
make scrape
```

This runs:

```text
ingestion.pipelines.ingest_reports
```

Use it when adding or refreshing annual reports.

### 5.2 Process reports

Generate narrative chunks and structured tables together:

```bash
make ingest
```

Equivalent to:

```bash
make chunks
make tables
```

To run either stage independently:

```bash
make chunks
make tables
```

Inspect an extracted table with:

```bash
make check_json_table
```

### 5.3 Build the retrieval index

After ingestion:

```bash
make build_index
```

This builds the keyword and vector retrieval structures used by the application.

The expected setup sequence is therefore:

```text
make db_start
      ↓
make scrape
      ↓
make ingest
      ↓
make build_index
```

If the reports are already downloaded, `make scrape` does not need to be repeated before rebuilding processed data.

---

## 6. Test Retrieval, RAG, and Agent Pipelines

### Retrieval

The Makefile provides fixed smoke queries for each retrieval mode:

```bash
make test_text_search
make test_vector_search
make test_hybrid_search
```

These test keyword, vector, and hybrid retrieval respectively using GTCO's 2023 profit-before-tax question.

### RAG

Run the default RAG query:

```bash
make test_rag
```

Customize it with Make variables:

```bash
make test_rag \
    QUERY="What was GTCO's profit before tax in 2023?" \
    MODE=hybrid \
    TOP_K=8 \
    TICKER=GTCO \
    YEAR=2023
```

Defaults:

```text
QUERY  = Who is the Group Chief Executive Officer?
MODE   = hybrid
TOP_K  = 20
```

The RAG target always prints the retrieved context.

### Agent

Run:

```bash
make test_agent
```

Or:

```bash
make test_agent \
    QUERY="Compare GTCO's profit before tax in 2023 and 2024." \
    TICKER=GTCO \
    TOP_K=8
```

Optional debugging flags:

```bash
SHOW_CONTEXT=1
SHOW_RAW_TOOLS=1
```

Example:

```bash
make test_agent \
    QUERY="Who is the Group Chief Executive Officer?" \
    SHOW_CONTEXT=1 \
    SHOW_RAW_TOOLS=1
```

---

## 7. Run the Application

The local application consists of:

```text
Streamlit → FastAPI → PostgreSQL + pgvector
```

Grafana runs alongside these services for local monitoring.

### Start everything

```bash
make app
```

This target:

1. starts PostgreSQL;
2. starts Grafana;
3. rebuilds the investor snapshot;
4. starts FastAPI;
5. starts Streamlit.

Local services are normally available at:

| Service | Address |
|---|---|
| Streamlit | `http://localhost:8501` |
| FastAPI | `http://localhost:8000` |
| FastAPI docs | `http://localhost:8000/docs` |
| Grafana | `http://localhost:3000` |

Press `Ctrl+C` to stop the locally spawned FastAPI and Streamlit processes. Then stop Docker services with:

```bash
make stop_app
```

### Run services independently

Useful for development and troubleshooting:

```bash
make postgres
make monitoring
make investor_snapshot
make backend
make frontend
```

`make backend` starts Uvicorn with automatic reload for the application source directories.

`make frontend` starts Streamlit using the `frontend` dependency group.

### Test the backend API

With FastAPI running:

```bash
make test_backend
```

This sends a sample RAG request to:

```text
POST /api/v1/query
```

---

## 8. Evaluation

### Generate a benchmark

```bash
make generate_eval
```

Default configuration:

```text
N=100
DATASET=data/evaluation/benchmark.jsonl
SEED=42
POOL_SIZE=2000
MIN_QUALITY=0.90
MIN_DIFFICULTY=0.80
MIN_FINANCIAL=0.90
```

Override values when required:

```bash
make generate_eval N=50 SEED=123
```

### Evaluate RAG

```bash
make eval_rag
```

Defaults to hybrid retrieval with `TOP_K=8`.

Examples:

```bash
make eval_rag MODE=keyword
make eval_rag MODE=vector
make eval_rag MODE=hybrid LIMIT=10
```

### Evaluate the agent

```bash
make eval_agent
```

For a smaller run:

```bash
make eval_agent LIMIT=10
```

---

## 9. Testing and Code Quality

### Fast test suite

```bash
make test_fast
```

This runs the smoke and integration tests under:

```text
tests/smoke
tests/integration
```

### Formatting and linting

Format code:

```bash
make format
```

Check formatting without modifying files:

```bash
make format_check
```

Run Pylint:

```bash
make lint
```

Run all quality checks:

```bash
make quality
```

Run all configured pre-commit hooks:

```bash
make precommit
```

A typical pre-commit workflow is:

```bash
make format
make quality
make test_fast
make precommit
```

---

## 10. Local Monitoring

Start PostgreSQL and Grafana:

```bash
make postgres
make monitoring
```

Grafana is available at:

```text
http://localhost:3000
```

The dashboard and PostgreSQL datasource are provisioned from the repository, so dashboard panels do not need to be recreated manually.

Generate synthetic application traffic with:

```bash
make synthetic_test REQUESTS=20
```

The Makefile uses:

```text
--delay 3
--pipeline mixed
```

`REQUESTS` must be provided when calling this target.

Monitoring telemetry is stored in:

```text
monitoring.sessions
monitoring.interactions
monitoring.llm_calls
monitoring.feedback
```

---

## 11. Railway Deployment

The production architecture uses separate Railway services for FastAPI and PostgreSQL.

### PostgreSQL

Create a PostgreSQL service and ensure pgvector is enabled:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Railway manages its own database credentials. Do not commit them to the repository.

### FastAPI

Configure the backend's production database variable to reference the Railway PostgreSQL service. For the current application configuration:

```text
DESTINATION__POSTGRES__CREDENTIALS=${{Postgres.DATABASE_URL}}
```

Replace `Postgres` if the Railway database service has a different name.

Use Railway's assigned port in the production start command:

```bash
python -m uvicorn deployment.backend.main:app \
    --host 0.0.0.0 \
    --port $PORT
```

After deployment, generate a public domain for the FastAPI service and configure the frontend to use that backend URL.

The PostgreSQL service does not need permanent public networking.

---

## 12. Sync Production Monitoring Data Locally

Grafana remains local. Production telemetry can be copied from Railway PostgreSQL into the local `monitoring` schema.

### Requirements

Install and authenticate the Railway CLI, then link the project:

```bash
railway link
```

The current Makefile also expects PostgreSQL 18 client tools through Homebrew:

```bash
brew install postgresql@18
```

Verify:

```bash
$(brew --prefix postgresql@18)/bin/pg_dump --version
```

Add the Railway database password to `.env`:

```env
RAILWAY_POSTGRES_PASSWORD=<railway-password>
```

The local `POSTGRES_PASSWORD` must also be configured.

### Synchronize monitoring data

Terminal 1:

```bash
make railway-tunnel
```

This opens a local tunnel on port `55432` by default.

Keep it running.

Terminal 2:

```bash
make sync-monitoring-from-railway
```

The synchronization process:

```text
Railway monitoring schema
          ↓
      pg_dump
          ↓
truncate local monitoring tables
          ↓
     pg_restore
          ↓
    Local Grafana
```

Only data from the `monitoring` schema is copied. The local financial-report and retrieval data are not replaced.

> The sync target clears the existing local monitoring rows before restoring the Railway monitoring data.

---

## 13. Common Development Workflow

For normal application development:

```text
uv sync
   ↓
make postgres
   ↓
make backend + make frontend
   ↓
make format
   ↓
make quality
   ↓
make test_fast
```

Or start the complete local environment with:

```bash
make app
```

For data-pipeline changes:

```text
make db_start
   ↓
make scrape          # only when reports need downloading
   ↓
make ingest
   ↓
make build_index
   ↓
make test_hybrid_search
   ↓
make test_rag
```

For production monitoring:

```text
Generate production traffic
          ↓
make railway-tunnel
          ↓
make sync-monitoring-from-railway
          ↓
Refresh local Grafana
```

---

## 14. Makefile Command Reference

| Command | Purpose |
|---|---|
| `make db_start` | Start ingestion PostgreSQL |
| `make db_stop` | Stop ingestion Docker Compose stack |
| `make psql` | Open PostgreSQL shell |
| `make scrape` | Download/ingest annual reports |
| `make chunks` | Generate narrative chunks |
| `make tables` | Extract structured tables |
| `make ingest` | Run chunks + tables |
| `make check_json_table` | Inspect an extracted table |
| `make notebook` | Start Jupyter Notebook |
| `make build_index` | Build retrieval index |
| `make test_text_search` | Test keyword retrieval |
| `make test_vector_search` | Test vector retrieval |
| `make test_hybrid_search` | Test hybrid retrieval |
| `make test_rag` | Run RAG pipeline |
| `make test_agent` | Run agent pipeline |
| `make generate_eval` | Generate evaluation benchmark |
| `make eval_rag` | Evaluate RAG |
| `make eval_agent` | Evaluate agent |
| `make postgres` | Start root PostgreSQL service |
| `make monitoring` | Start Grafana |
| `make investor_snapshot` | Rebuild frontend investor metrics |
| `make backend` | Start FastAPI development server |
| `make frontend` | Start Streamlit |
| `make app` | Start the complete local application |
| `make stop_app` | Stop root Docker Compose services |
| `make test_backend` | Send a sample request to FastAPI |
| `make synthetic_test REQUESTS=N` | Generate synthetic traffic |
| `make test_fast` | Run smoke and integration tests |
| `make format` | Format Python code |
| `make format_check` | Check formatting |
| `make lint` | Run Pylint |
| `make quality` | Run formatting checks + lint |
| `make precommit` | Run all pre-commit hooks |
| `make railway-tunnel` | Open Railway PostgreSQL tunnel |
| `make sync-monitoring-from-railway` | Copy Railway monitoring data locally |

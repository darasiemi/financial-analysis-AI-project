# System Architecture

This document describes the architecture of my Financial Analysis AI system, including data ingestion, retrieval, analysis pipelines, deployment, monitoring, and observability. 

For installation and deployment instructions, see `SETUP.md`.

---

## 1. System Overview

The system provides AI-assisted financial analysis over corporate annual reports using both Retrieval-Augmented Generation (RAG) and agentic workflows.

```text
Annual Reports
      │
      ▼
Ingestion + PDF Processing
      │
      ▼
PostgreSQL + pgvector
      │
      ▼
Retrieval Index
      │
      ├───────────────┐
      ▼               ▼
     RAG            Agent
      │               │
      └───────┬───────┘
              ▼
            Gemini
              │
              ▼
        FastAPI Backend
              │
              ▼
      Streamlit Frontend
```

The main components are:

| Component | Responsibility |
|---|---|
| Streamlit | User interface |
| FastAPI | API and pipeline orchestration |
| PostgreSQL | Financial data, retrieval data, and monitoring telemetry |
| pgvector | Vector similarity search |
| Gemini | Answer generation, agent reasoning, and relevance judging |
| Grafana | Local monitoring and observability |
| Railway | Production hosting for FastAPI and PostgreSQL |

---

## 2. Data Ingestion and Processing

The ingestion pipeline downloads annual reports from selected Nigerian listed companies using `requests` for direct downloads and Playwright for JavaScript-protected sources.

Reports are validated for PDF integrity, reporting year, and duplicates. SHA-256 hashes are used for file identification and deduplication.

Validated reports are processed into two retrieval-ready forms:

- **Narrative chunks:** extracted with PyMuPDF, reordered using layout information, cleaned, reconstructed into paragraphs, and split into overlapping section-aware chunks.
- **Financial tables:** extracted separately, stored as structured JSON, and converted to RAG-friendly text for retrieval.

Processed data is loaded into PostgreSQL using `dlt`.

```text
Annual Report PDFs
        │
        ▼
    PyMuPDF
        │
   ┌────┴─────┐
   ▼          ▼
Narrative   Tables
Chunks      JSON + RAG Text
   │          │
   └────┬─────┘
        ▼
       dlt
        │
        ▼
   PostgreSQL
```

Each retrieval document retains source metadata such as company, reporting year, page range, section title, and content type.

---

## 3. Retrieval Layer

Narrative chunks and table representations are combined into a unified retrieval index.

The system supports three retrieval strategies:

- **Keyword search:** PostgreSQL Full-Text Search for lexical matching.
- **Semantic search:** SentenceTransformer embeddings stored with pgvector.
- **Hybrid search:** Reciprocal Rank Fusion (RRF) combining keyword and vector results.

The original structured JSON representation of financial tables is preserved so exact rows, columns, and values remain accessible when required.

```text
Narrative Chunks ───────┐
                        ├──► Unified Retrieval Index
Table RAG Text ─────────┘
                              │
                      ┌───────┴────────┐
                      ▼                ▼
                 Keyword Search   Vector Search
                      │                │
                      └───────┬────────┘
                              ▼
                         Hybrid Search
```

---

## 4. RAG Pipeline

The RAG pipeline handles evidence-grounded financial question answering.

Flow:

```text
User Question
      │
      ▼
Keyword / Semantic / Hybrid Retrieval
      │
      ▼
Top-K Evidence
      │
      ▼
Context Construction
      │
      ▼
Gemini
      │
      ▼
Grounded Answer + Sources
```

Retrieval can be filtered by company and reporting year.

The generated context contains both the retrieved evidence and its metadata. Gemini is instructed to answer from the supplied evidence and preserve financial values, currencies, units, periods, and entity distinctions.

If no relevant evidence is retrieved, the pipeline returns an insufficient-evidence response rather than generating an unsupported answer.

---

## 5. Agentic Financial Analysis

The agent pipeline extends the RAG pipeline for more complex tasks.

It begins with hybrid retrieval and allows Gemini to invoke additional tools when the initial evidence is insufficient.

Available tools include:

| Tool | Purpose |
|---|---|
| Keyword Search | Exact terms, metrics, names, and accounting terminology |
| Semantic Search | Conceptually related passages and tables |
| Hybrid Search | Combined lexical and semantic retrieval |
| Table Lookup | Exact structured table data |
| Calculator | Deterministic calculations |
| Web Search | Current or external information |
| PowerPoint Generation | Generates `.pptx` financial-analysis presentations |

Source priority is:

1. Local annual reports
2. Structured extracted tables
3. Deterministic calculations
4. Public web information

```text
User Question
      │
      ▼
Initial Hybrid Retrieval
      │
      ▼
Gemini Agent
      │
      ├── Retrieval
      ├── Table Lookup
      ├── Calculator
      ├── Web Search
      └── PowerPoint Generation
      │
      ▼
Final Response / Presentation
```

Tool calls are retained for traceability and debugging.

---

## 6. Evaluation

The evaluation framework compares keyword, semantic, hybrid RAG, and agentic pipelines using a financially focused benchmark.

The benchmark contains synthetic question-answer pairs generated from indexed annual reports and independently validated for grounding, financial relevance, difficulty, calculation validity, entity/period/unit consistency, and naturalness.

Evaluation includes:

- Precision@K
- Recall@K
- Hit Rate@K
- MRR
- nDCG@K
- Token F1
- LLM-based correctness
- Faithfulness
- Relevance
- Latency
- Agent tool traces

Current hybrid RAG results:

| Metric | Score |
|---|---:|
| Precision@8 | 0.079 |
| Recall@8 | 0.446 |
| Hit Rate@8 | 0.523 |
| MRR | 0.380 |
| nDCG@8 | 0.369 |
| Answer Token F1 | 0.474 |
| Answer Correctness | 0.779 |
| Faithfulness | **0.969** |
| Answer Relevance | **0.904** |
| Average Latency | 9.88 s |
| Successfully Evaluated | 65 / 75 |

The main limitation is retrieval quality: generation is generally strong when the required evidence is successfully retrieved.

More details are available in `evaluation/README.md`.

---

## 7. Application and Deployment Architecture

The deployed application uses three layers:

```text
User
 │
 ▼
Streamlit Frontend
 │
 │ HTTPS / JSON
 ▼
FastAPI Backend
 │
 ├── RAG
 ├── Agent
 ├── Gemini
 └── Monitoring
 │
 ▼
Railway PostgreSQL + pgvector
```

### Streamlit

The frontend collects questions and configuration options, calls the FastAPI backend, and displays answers, evidence, charts, generated files, and feedback controls.

### FastAPI

The backend exposes the application API and orchestrates RAG, agent execution, database access, Gemini calls, and monitoring.

Main endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Backend/database health |
| `GET` | `/api/v1/filters` | Available companies and years |
| `GET` | `/api/v1/stats` | Corpus statistics |
| `POST` | `/api/v1/query` | Run RAG or Agent analysis |
| `POST` | `/api/v1/feedback` | Save user feedback |

### PostgreSQL + pgvector

PostgreSQL stores both retrieval data and monitoring telemetry. pgvector provides vector similarity search.

FastAPI and PostgreSQL are deployed as separate Railway services and communicate through Railway's private network.

---

## 8. Monitoring and Observability

Monitoring is persisted in the `monitoring` schema.

Main tables:

```text
monitoring.sessions
monitoring.interactions
monitoring.llm_calls
monitoring.feedback
```

The monitoring layer separates four types of signals:

- **System behaviour:** status, pipeline, latency
- **Model usage:** tokens, model calls, estimated cost
- **Automated quality:** relevance judge
- **Human feedback:** thumbs up/down

### Interaction Telemetry

`monitoring.interactions` stores request-level information including:

```text
response_id
pipeline
question
answer
status
created_at
completed_at
total_latency_seconds
latencies
application_*_tokens
application_cost_usd
judge_status
relevance_score
judge_latency_seconds
judge_cost_usd
```

`monitoring.llm_calls` stores individual LLM-call telemetry, allowing one interaction to contain multiple application calls plus a judge call.

### Relevance Judge

An asynchronous Gemini judge evaluates question-answer relevance after the response has been returned.

Possible states are:

```text
pending
completed
failed
skipped
```

Judge sampling is controlled with `MONITORING_JUDGE_SAMPLE_RATE`, allowing evaluation coverage to be balanced against cost.

### User Feedback

Users can submit:

```text
1   thumbs up
-1  thumbs down
```

Feedback is stored independently from automated relevance scores.

---

## 9. Grafana Monitoring Architecture

Grafana is run locally rather than deployed.

Railway PostgreSQL remains the production source of truth. Monitoring data is synchronized on demand to the local PostgreSQL instance over an SSH tunnel.

```text
Railway FastAPI
      │
      ▼
Railway PostgreSQL
      │
      │ SSH tunnel + monitoring sync
      ▼
Local PostgreSQL
      │
      ▼
Local Grafana
```

This avoids permanently exposing the production database and keeps Grafana outside the production deployment.

The dashboard includes:

- Total Responses
- Average Latency
- Application Cost
- Judge Cost
- Average Relevance
- Thumbs-Up Rate
- Response Volume Over Time
- Latency Over Time
- Application vs Judge Cost
- Average Latency by Pipeline
- User Feedback by Pipeline
- Answer Relevance Over Time
- Recent Interactions
- Knowledge Base Statistics

---

## 10. Precomputed Investor Growth Comparison

The Streamlit landing page includes a precomputed comparison across GTCO, Zenith Bank, and MTN Nigeria using two consistent Group-level measures:

- Total Assets Growth
- Profit After Tax Growth

Verified source values are stored in:

```text
data/frontend/investor_metrics_source.json
```

The preprocessing script:

```text
scripts/build_investor_snapshot.py
```

produces:

```text
data/frontend/investor_metrics.json
```

This avoids database retrieval or LLM inference during page load and keeps the displayed headline metrics deterministic and auditable.

---

## 11. Security and Design Decisions

The architecture follows several practical principles:

- Railway PostgreSQL remains private.
- FastAPI communicates with PostgreSQL through Railway's internal network.
- Production database access from local development uses a temporary SSH tunnel.
- Secrets are stored in `.env` or Railway environment variables and are not committed to source control.
- Grafana remains local because it is currently used for development and monitoring rather than as a public production service.
- Production monitoring data and local test telemetry are kept separate.

---

## 12. End-to-End Flow

```text
Annual Reports
      │
      ▼
Ingestion + Processing
      │
      ▼
PostgreSQL + pgvector
      │
      ▼
Retrieval Index
      │
      ├───────────┐
      ▼           ▼
     RAG        Agent
      │           │
      └─────┬─────┘
            ▼
          Gemini
            │
            ▼
      FastAPI Backend
            │
            ▼
     Streamlit Frontend
            │
            ├── User Feedback
            │
            ▼
   Monitoring Telemetry
            │
            ▼
   Railway PostgreSQL
            │
            ▼
 Local PostgreSQL + Grafana
```

This design keeps retrieval, reasoning, deployment, and observability modular while maintaining a single PostgreSQL-based data layer for financial content and production telemetry.


## 13. System Design Trade-offs

I made several design changes as the project evolved to balance extraction quality, retrieval accuracy, system complexity, and evaluation reliability.

1. **I separated narrative and table processing.**  
   Annual-report prose and financial tables require different processing to preserve their meaning, so I used separate pipelines for them. Narrative content was reconstructed and chunked for retrieval, while tables were extracted independently. Detected table regions were excluded from narrative chunks to reduce duplication. Two-column page layouts were still treated as narrative content rather than tables, with their reading order reconstructed before chunking.

2. **I switched table storage from relational normalization to JSON.**  
   I initially attempted to represent extracted tables relationally, but annual-report tables vary considerably in structure and were not being preserved reliably. I therefore stored each table as structured JSON, retaining its rows, columns, labels, and values without forcing different tables into a common schema. I also maintained a textual representation of each table for retrieval and embeddings.

3. **I used layout-aware chunking rather than splitting raw PDF text.**  
   I reconstructed narrative content from the PDF layout and use paragraph- and section-aware chunking with controlled chunk sizes and overlap. This required more preprocessing than fixed character splitting, but produced more coherent retrieval units and better preserved the context of financial-report narratives.

4. **I kept lexical and vector retrieval in PostgreSQL using pgvector.**  
   I containerized the PostgreSQL database using Docker to make the database environment reproducible, portable, and easier to set up consistently across development environments. I used the `pgvector` PostgreSQL image so that report metadata, extracted content, full-text search, and vector embeddings can remain within the same database rather than introducing a separate vector store. I combined lexical and semantic retrieval through hybrid search: keyword search handles exact financial terminology well, while vector search helps when questions and reports use different wording.

5. **I kept the agent lightweight and grounded it in RAG first.**  
   The agent starts with hybrid retrieval over the annual-report corpus and invokes additional tools—such as keyword or semantic search, structured table lookup, deterministic calculation, web search, and report generation—only when needed. This provides more flexibility than a fixed RAG pipeline while avoiding the orchestration complexity of a multi-agent system.

6. **I redesigned the benchmark when the initial synthetic evaluation was too easy.**  
   The initial generator often produced simple lookup questions, governance facts, and even questions influenced by extraction artifacts such as generic table columns. I shifted generation toward harder tasks such as table reasoning, calculations, within-source and cross-report comparisons, multi-hop retrieval, and financial interpretation. I also introduced stratified sampling across companies and reporting years and validation for grounding, financial relevance, difficulty, and data consistency.

7. **I added validation and stratified sampling because synthetic benchmarks can otherwise be misleading.**  
   The benchmark is now sampled across ticker and report year rather than whichever documents happen to appear first in the database. Generated questions are also checked for financial relevance, difficulty, grounding, unit consistency, calculation validity, and semantic compatibility. This improves benchmark quality, although I still mark synthetic examples as not human-verified because LLM-generated ground truth can contain errors.

8. **I designed the repository for modularity and reproducibility.**  
   I separated ingestion, processing, indexing, retrieval, RAG, agent tools, and evaluation into modular components that can be run and tested independently. I use `Docker` for a consistent PostgreSQL environment, `uv` for dependency management, environment-based configuration, and a `Makefile` to standardize common workflows. Benchmark generation also supports a configurable random seed, although database-level random sampling means generation is not fully deterministic.

9. **I used LLM validation for scalability, but retained human verification for the final gold benchmark.**  
Because manually creating and validating a sufficiently challenging financial-analysis benchmark is time-consuming, I used an **LLM validator** to automatically screen synthetic question-answer pairs. However, LLM validation can still accept subtle factual errors, unsupported interpretations, or artificially difficult questions. I therefore keep accepted examples marked as synthetic and require **human verification before treating the benchmark as gold-standard ground truth**. This is future work considering the time constraint to deliver my project for the Zoomcamp.

10. **I configured CPU-only PyTorch to reduce deployment overhead.**  
    `sentence-transformers` depends on PyTorch, whose default resolution pulled in large CUDA/NVIDIA packages that were unnecessary for the current CPU-based deployment and caused Docker builds to exceed available disk space. I therefore used CPU-only PyTorch, trading GPU acceleration for a substantially lighter deployment.

11. **I separated the frontend, backend, and database, which were initially coupled within the Streamlit application.**  
    Initially, Streamlit handled the user interface while also directly invoking the RAG/agent logic and accessing PostgreSQL. I separated these responsibilities by using Streamlit solely as the frontend, introducing FastAPI as the backend for RAG, agent orchestration, and database access, and keeping PostgreSQL/pgvector as the independent data layer. This separation adds API and service-orchestration complexity, but provides clearer separation of concerns, improves maintainability and testability, enables the frontend and backend to scale or evolve independently, and makes it easier to support additional clients beyond Streamlit in the future.

12. **I separated development and deployment dependencies and workflows to address disk-space constraints and keep deployment lean.**  
    After Docker builds exhausted the available disk space on my machine, I separated development dependencies, such as ingestion, notebooks, evaluation, and document processing, from the frontend and backend runtime dependencies. I also used a Makefile for local development and Docker Compose for fully containerized deployment. This reduces unnecessary deployment dependencies while improving maintainability and reproducibility.

13. **I chose PostgreSQL over a document database to support both application data and monitoring.**  
    Although a document database such as MongoDB can provide greater flexibility for storing semi-structured JSON which I used for my data-RAG pipeline, PostgreSQL better fits the application's combination of structured financial data, retrieval metadata, user interactions, feedback, latency, cost, and evaluation metrics, while still supporting semi-structured data through `JSONB`. PostgreSQL also integrates directly with Grafana, allowing monitoring metrics to be queried using SQL without introducing a separate database.



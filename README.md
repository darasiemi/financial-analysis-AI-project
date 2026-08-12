# Nigeria Stock Financial Analysis Project

## Introduction

This is a final project for the Data Talks Club LLM [Zoomcamp](https://datatalks.club/docs/courses/llm-zoomcamp/) . In this project, I have implemented the end-to-end

## Data Ingestion

The ingestion pipeline automatically downloads annual reports from selected Nigerian listed companies, using **Requests** for direct downloads and **Playwright** for JavaScript-protected sources. Reports are validated for PDF integrity, reporting year, and duplicates, with **SHA-256 hashing** used for file identification and integrity checks. Validated reports and their metadata are then ingested into **PostgreSQL using dlt**, providing the source data for the downstream PDF processing, indexing, and retrieval pipelines.

### PDF Processing Pipeline

The PDF processing pipeline transforms annual reports into structured, retrieval-ready narrative chunks and financial tables.

- **Layout-aware PDF extraction.**  
  I used **PyMuPDF** to extract text blocks together with layout information such as bounding boxes, font size, and font style. The pipeline filters repeated headers and footers, contents pages, decorative elements, and other low-information artifacts before reconstructing the document text.

- **Reading-order and document reconstruction.**  
  Extracted blocks are reordered to reconstruct coherent narrative content across both single- and two-column layouts. Paragraph boundaries and section headings are identified using layout, textual, and typographical features, producing cleaner document structure than the raw PDF extraction order.

- **Narrative chunk generation.**  
  Reconstructed paragraphs are converted into overlapping, section-aware chunks with configurable size and overlap. Each chunk includes metadata such as the report ID, ticker, reporting year, page range, section title, word and token counts, and a content hash for traceability and deduplication.

- **Structured table extraction.**  
  Tables are processed through a separate extraction path. Each table is represented as structured **JSON** and is also converted into RAG-friendly text for embedding and retrieval. Table metadata includes its report, page, title, dimensions, and content hash.

- **Data ingestion and indexing.**  
  **dlt** loads the processed narrative chunks and tables into **PostgreSQL**. Embeddings are stored using **pgvector**, while PostgreSQL full-text indexing supports lexical search, providing the indexed knowledge base used by the downstream RAG and agent pipelines.

The resulting flow is:

```text
Annual Report PDFs
        │
        ▼
   PyMuPDF Parsing
        │
        ├──────────────────────┐
        ▼                      ▼
Narrative Processing      Table Extraction
        │                      │
Reading-Order             Structured JSON
Reconstruction            + RAG Text
        │                      │
Paragraph Reconstruction       │
        │                      │
Chunking                       │
        │                      │
        └──────────┬───────────┘
                   ▼
             dlt Ingestion
                   │
                   ▼
              PostgreSQL
                   │
          ┌────────┴────────┐
          ▼                 ▼
    Full-Text Index      pgvector
          │                 │
          └────────┬────────┘
                   ▼
             RAG / Agent

 ```             
## Retrieval Index

The retrieval pipeline creates a unified searchable index from both narrative text and financial tables. Each document retains metadata about its source, such as the company, reporting year, page, and content type, and is indexed for both **keyword and semantic search**. Dense embeddings are generated using a **SentenceTransformer** model and stored in PostgreSQL with **pgvector**, while full-text indexing supports lexical retrieval. The original structured representation of financial tables is preserved separately so that exact rows, columns, and values can be accessed when needed for financial analysis.

## Search

The project supports three retrieval strategies:

- **Keyword Search:** Uses PostgreSQL Full-Text Search (FTS) to retrieve documents based on lexical similarity, making it effective for exact financial terms and values.
- **Vector/Semantic Search:** Uses dense embeddings stored with `pgvector` to retrieve semantically similar documents, allowing relevant information to be found even when the query wording differs from the source text.
- **Hybrid Search:** Combines keyword and vector retrieval using Reciprocal Rank Fusion (RRF), leveraging the strengths of both lexical and semantic search to improve overall retrieval quality.

 Narrative passages and financial tables are processed separately but combined into a **single retrieval index**. Tables are converted to a text representation so they can be searched and ranked alongside narrative chunks using keyword, semantic, or hybrid retrieval. The original tables are preserved as structured **JSON**, allowing the system to access their rows, columns, and values when detailed table reasoning is required.

 ```

Narrative Pipeline                    Table Pipeline
       │                                    │
       ▼                                    ▼
Narrative Chunks                   Structured Table JSON
       │                                    │
       │                              Table → RAG Text
       │                                    │
       └──────────────┬─────────────────────┘
                      ▼
              Unified Retrieval Index
                      │
             ┌────────┴────────┐
             ▼                 ▼
       Keyword Search      Vector Search
             │                 │
             └────────┬────────┘
                      ▼
                Hybrid Search
                     (RRF)
```
### RAG Pipeline

The RAG pipeline retrieves relevant evidence from the indexed annual reports, constructs a grounded context, and uses **Gemini** to generate the final answer.

- **Configurable retrieval.**  
  The pipeline supports **keyword, semantic, and hybrid search**, with hybrid retrieval used by default. Queries can also be filtered by company and reporting year.

- **Context construction.**  
  Retrieved narrative passages and table representations are assembled into a structured context with their source metadata, including content type, company, reporting year, page range, and section.

- **Grounded answer generation.**  
  The retrieved context and user question are passed to **Gemini**, which is instructed to answer only from the supplied evidence, preserve financial values, currencies, units, periods, and entity distinctions, and cite the supporting retrieved sources.

- **Insufficient evidence handling.**  
  If retrieval returns no relevant documents, the pipeline does not generate an unsupported answer and instead reports that no relevant evidence was retrieved.

```text
User Question
      │
      ▼
Retrieval
(Keyword / Semantic / Hybrid)
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
Grounded Answer + Source Citations
```

## Agentic Financial Analysis

The project includes a lightweight agentic AI layer built on top of the RAG pipeline. Instead of relying on a single retrieval step, Gemini can inspect retrieved evidence and autonomously select additional tools when needed.

### Architecture

The agent follows a two-stage workflow:

1. **Initial Retrieval**
   - Hybrid search is performed over the indexed annual reports.
   - Retrieved narrative chunks and tables are supplied to Gemini as initial evidence.
   - Local annual reports remain the primary source of financial information.

2. **Agent Reasoning and Tool Use**
   - Gemini evaluates the initial evidence.
   - If sufficient, it answers directly.
   - Otherwise, it can perform additional retrieval, inspect structured tables, calculate values, search the web, or generate a PowerPoint presentation.

```text
User Question
      │
      ▼
Initial Hybrid Retrieval
      │
      ▼
Annual Report Context
      │
      ▼
Gemini Agent
      │
      ├── Keyword Search
      ├── Semantic Search
      ├── Hybrid Search
      ├── Table Lookup
      ├── Calculator
      ├── Web Search
      └── PowerPoint Generation
      │
      ▼
Final Response / Presentation
```

### Agent Tools

| Tool | Purpose |
| --- | --- |
| **Hybrid Search** | Combines lexical and semantic retrieval using Reciprocal Rank Fusion (RRF). |
| **Keyword Search** | Retrieves exact names, financial metrics, executive titles, and accounting terminology. |
| **Semantic Search** | Retrieves conceptually similar narrative chunks and tables using embeddings. |
| **Table Lookup** | Retrieves the original structured JSON for an extracted table when exact values or row/column relationships are required. |
| **Calculator** | Performs deterministic calculations such as percentage changes, ratios, margins, and differences. |
| **Web Search** | Uses Gemini with Google Search grounding for current or external information. |
| **PowerPoint Generation** | Creates designed `.pptx` presentations containing metrics, comparisons, charts, highlights, summaries, and sources. |

### Source Priority

The agent prioritizes evidence in the following order:

1. Local annual reports
2. Structured extracted tables
3. Deterministic calculations
4. Public web information

Web search is primarily used when information is current, external, or unavailable in the indexed reports.

### PowerPoint Generation

When explicitly requested, the agent can gather evidence, perform calculations, and generate a designed PowerPoint presentation.

Supported slide types include:

- Bullet summaries
- Financial metric cards
- Year-on-year comparisons
- Key figure highlights
- Charts
- Source/reference slides

Presentations are saved to:

```text
outputs/
```


### Tool Traceability

The CLI reports the initial retrieval query and the additional tools selected by Gemini, including their arguments and responses.

```text
Tool: search_keyword
Arguments:
  ticker: GTCO
  report_year: 2023
  query: Profit before tax

Tool: calculate
Arguments:
  expression: ...

Tool: create_powerpoint
Arguments:
  title: GTCO Profit Before Tax Analysis
  ...

Tool response:
  Status: SUCCESS
```

This makes the agent workflow inspectable and helps evaluate how retrieval, tool selection, and query refinement contribute to the final result.


## Evaluation

The evaluation framework provides a consistent way to compare the **keyword, semantic, hybrid RAG, and agentic financial-analysis pipelines** using the same financially focused benchmark. Because no labelled ground-truth dataset was initially available, I generated and validated synthetic benchmark questions from the indexed annual reports, with stratified sampling across companies and reporting years and an emphasis on challenging tasks such as table reasoning, calculations, cross-report comparisons, and multi-hop analysis. Retrieval is assessed using **Precision@K, Recall@K, Hit Rate@K, MRR, and nDCG@K**, while answer quality is evaluated using **Token F1** and LLM-based measures of **correctness, faithfulness, and relevance**. Agent runs additionally retain tool-call traces and execution timing to support detailed analysis of retrieval, reasoning, and tool-use failures.

**How synthetic benchmark validation was done***: Each synthetic question-answer pair is independently evaluated by an LLM validator for evidence grounding, financial relevance, difficulty, calculation validity, entity/period/unit consistency, and naturalness. Examples are retained only if they achieve a minimum **quality score of 0.90**, **difficulty score of 0.80**, and **financial relevance score of 0.90**. The current benchmark targets **75 accepted examples**, with `gemini-2.5-flash` used for both generation and validation. Accepted examples remain marked as synthetic and not human-verified until manually reviewed.

```
                    Benchmark
                        │
                        ▼
                 Run RAG / Agent
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
      Retrieval      Generated     Retrieved
       Sources        Answer        Context
          │             │             │
          ▼             ▼             │
   Gold Source IDs  Reference Answer  │
          │             │             │
          ▼             └──────┬──────┘
 Deterministic Metrics         ▼
 Precision / Recall      Gemini LLM Judge
 Hit Rate / MRR / nDCG          │
                               ├── Correctness
 Generated ↔ Reference          ├── Faithfulness
          │                     └── Relevance
          ▼
       Token F1
```

[More on evaluation](evaluation/README.md)

## Deployment

The application is deployed as a **three-layer architecture**, separating the **Streamlit frontend**, **FastAPI backend**, and **PostgreSQL/pgvector database**. The frontend provides the user interface, while the backend exposes an API that handles financial-analysis requests, RAG and agent execution, and database access.

### Deployment Architecture

```text
                         User
                           │
                           ▼
                ┌─────────────────────┐
                │ Streamlit Frontend  │
                │      Port 8501      │
                │                     │
                │ • User interface    │
                │ • Query controls    │
                │ • Results & charts  │
                └──────────┬──────────┘
                           │
                      HTTP / JSON
                           │
                           ▼
                ┌─────────────────────┐
                │   FastAPI Backend   │
                │      Port 8000      │
                │                     │
                │ • API endpoints     │
                │ • RAG pipeline      │
                │ • Agent pipeline    │
                │ • Gemini calls      │
                │ • Database access   │
                └──────────┬──────────┘
                           │
                    PostgreSQL
                           │
                           ▼
                ┌─────────────────────┐
                │ PostgreSQL/pgvector │
                │                     │
                │ • Report chunks     │
                │ • Metadata          │
                │ • Embeddings        │
                └─────────────────────┘
```

### Frontend

The **Streamlit frontend** is responsible only for presentation and user interaction. It collects financial-analysis questions and configuration options, sends requests to the FastAPI backend over HTTP, and presents the returned answers, evidence, agent traces, statistics, and visualizations.

### Backend

The **FastAPI backend** provides the application API and contains the core financial-analysis orchestration. It receives requests from Streamlit and routes them through either the standard **RAG pipeline** or the **agentic pipeline**.

The backend also handles retrieval, Gemini interactions, tool execution, and access to PostgreSQL/pgvector. This prevents the frontend from directly interacting with the database or analysis pipelines.

The backend exposes:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Checks backend and database availability |
| `GET` | `/api/v1/filters` | Returns available companies and reporting years |
| `GET` | `/api/v1/stats` | Returns corpus statistics |
| `POST` | `/api/v1/query` | Executes RAG or agent-based financial analysis |

### Database

**PostgreSQL with pgvector** provides the persistence and retrieval layer. It stores the processed annual-report content, associated metadata, and vector embeddings used by the retrieval pipelines.

### Containerized Deployment

For a fully containerized deployment, **Docker Compose** orchestrates the frontend, backend, and database as separate services:

```text
Docker Compose
│
├── frontend
│   └── Streamlit
│
├── backend
│   └── FastAPI
│       ├── RAG
│       ├── Agent
│       └── Gemini
│
└── postgres
    └── PostgreSQL + pgvector
```

Each application layer can therefore be developed, tested, and deployed independently while Docker Compose provides a reproducible environment for running the complete system.

## Design Trade-offs

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

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

The evaluation framework provides a consistent way to compare the **keyword, semantic, hybrid RAG, and agentic financial-analysis pipelines** using the same financially focused benchmark. Because no labelled ground-truth dataset was initially available, I generate and validate synthetic benchmark questions from the indexed annual reports, with stratified sampling across companies and reporting years and an emphasis on challenging tasks such as table reasoning, calculations, cross-report comparisons, and multi-hop analysis. Retrieval is assessed using **Precision@K, Recall@K, Hit Rate@K, MRR, and nDCG@K**, while answer quality is evaluated using **Token F1** and LLM-based measures of **correctness, faithfulness, and relevance**. Agent runs additionally retain tool-call traces and execution timing to support detailed analysis of retrieval, reasoning, and tool-use failures.

[More on evaluation](evaluation/README.md)


## Design Trade-offs

I made several design changes as the project evolved to balance extraction quality, retrieval accuracy, system complexity, and evaluation reliability.

1. **I separated narrative and table processing.**  
   Annual-report prose and financial tables require different processing to preserve their meaning, so I used separate pipelines for them. Narrative content was reconstructed and chunked for retrieval, while tables were extracted independently. Detected table regions were excluded from narrative chunks to reduce duplication. Two-column page layouts were still treated as narrative content rather than tables, with their reading order reconstructed before chunking.

2. **I switched table storage from relational normalization to JSON.**  
   I initially attempted to represent extracted tables relationally, but annual-report tables vary considerably in structure and were not being preserved reliably. I therefore stored each table as structured JSON, retaining its rows, columns, labels, and values without forcing different tables into a common schema. I also maintained a textual representation of each table for retrieval and embeddings.

3. **I use layout-aware chunking rather than splitting raw PDF text.**  
   I reconstructed narrative content from the PDF layout and use paragraph- and section-aware chunking with controlled chunk sizes and overlap. This required more preprocessing than fixed character splitting, but produced more coherent retrieval units and better preserved the context of financial-report narratives.

4. **I kept lexical and vector retrieval in PostgreSQL using pgvector.**  
   I containerized the PostgreSQL database using Docker to make the database environment reproducible, portable, and easier to set up consistently across development environments. I used the `pgvector` PostgreSQL image so that report metadata, extracted content, full-text search, and vector embeddings can remain within the same database rather than introducing a separate vector store. I combined lexical and semantic retrieval through hybrid search: keyword search handles exact financial terminology well, while vector search helps when questions and reports use different wording.

5. **I kept the agent lightweight and grounded it in RAG first.**  
   The agent starts with hybrid retrieval over the annual-report corpus and invokes additional tools—such as keyword or semantic search, structured table lookup, deterministic calculation, web search, and report generation—only when needed. This provides more flexibility than a fixed RAG pipeline while avoiding the orchestration complexity of a multi-agent system.

6. **I redesigned the benchmark when the initial synthetic evaluation was too easy.**  
   Early benchmark generation produced many simple factual or document-specific questions that did not adequately test financial analysis. I shifted generation toward harder tasks such as table reasoning, calculations, within-source and cross-report comparisons, multi-hop retrieval, and financial interpretation. I also introduced stratified sampling across companies and reporting years and validation for grounding, financial relevance, difficulty, and data consistency.

## Design Trade-offs

I made several key design changes as the project evolved, mainly to improve retrieval quality, financial reasoning, and evaluation reliability.

1. **I stored extracted tables as JSON rather than recreating them as relational PostgreSQL tables.**  
   Annual-report tables vary widely in structure, so mapping every table into a fixed relational schema would dehave required substantial table-specific logic. I instead store the structured table representation as JSON, which preserves rows, columns, labels, and values while keeping ingestion flexible. The trade-off is that SQL querying over individual table cells is less direct, so I use a dedicated table lookup tool when exact structure matters.

2. **I chunked narrative text but treated tables differently.**  
   I split long narrative sections into smaller retrieval chunks to improve search precision and reduce context size. However, chunking tables like normal text can destroy row-column relationships, so I preserve tables as structured units and index a searchable textual representation alongside the original JSON. This gives me both retrievability and structural fidelity.

3. **I kept retrieval in PostgreSQL and combined lexical and semantic search.**  
   I use PostgreSQL for document metadata, full-text retrieval, and vector embeddings rather than maintaining separate search systems. I then combine keyword and semantic retrieval using hybrid search. This keeps the architecture simpler while still handling both exact financial terminology and semantically similar wording.

4. **I moved from a simple RAG pipeline to a lightweight agent only where additional reasoning was useful.**  
   The system performs initial hybrid retrieval first, then lets Gemini decide whether it needs more retrieval, structured table lookup, calculation, web search, or report generation. I chose this instead of a fully autonomous multi-agent architecture because it keeps the annual reports as the primary evidence source and makes failures easier to trace.

5. **I changed the benchmark after finding that the first synthetic questions were too easy and too document-specific.**  
   The initial generator often produced simple lookup questions, governance facts, and even questions influenced by extraction artifacts such as generic table columns. These were useful for retrieval sanity checks but did not adequately test financial analysis. I redesigned generation to focus on harder tasks such as table reasoning, cross-year comparisons, percentage changes, ratios, multi-hop retrieval, and financial interpretation, while rejecting parser-oriented or trivial questions.

6. **I added validation and stratified sampling because synthetic benchmarks can otherwise be misleading.**  
   The benchmark is now sampled across ticker and report year rather than whichever documents happen to appear first in the database. Generated questions are also checked for financial relevance, difficulty, grounding, unit consistency, calculation validity, and semantic compatibility. This improves benchmark quality, although I still mark synthetic examples as not human-verified because LLM-generated ground truth can contain errors.
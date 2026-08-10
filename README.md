# Nigeria Stock Financial Analysis Project

## Introduction

This is a final project for the Data Talks Club LLM [Zoomcamp](https://datatalks.club/docs/courses/llm-zoomcamp/) . In this project, I have implemented the end-to-end

## Data Ingestion

The ingestion pipeline automatically downloads annual reports from selected Nigerian listed companies, validates each file (PDF integrity, report year, and duplicates), and stores them in a structured local directory for downstream processing. It uses `requests` for direct downloads, `Playwright` for JavaScript-protected sources, `PyMuPDF` for PDF validation, and SHA-256 hashing for file integrity. The downloaded reports serve as the primary data source for document parsing, embedding generation, and financial analysis.


The data ingestion pipeline processes downloaded annual reports and loads them into PostgreSQL using **dlt**. The pipeline extracts report metadata (company, report year, file path, checksum, page count) and page-level text using **PyMuPDF**, then stores the results in structured database tables (`reports` and `report_pages`). Each report undergoes validation for PDF integrity, report year, and text extraction quality, enabling reliable downstream processing for chunking, embedding generation, and retrieval-augmented financial analysis.

### PDF Processing Pipeline

### PDF Processing Pipeline

The PDF processing pipeline transforms raw annual reports into high-quality, retrieval-ready knowledge for the AI system. Using **PyMuPDF**, each report is parsed into layout-aware text blocks containing the extracted text, bounding-box coordinates, font properties, and page metadata. Rather than relying on the raw extraction order—which often produces fragmented or interleaved text in complex financial reports—the pipeline reconstructs each page by determining the correct reading order for both single-column and multi-column layouts. It automatically removes repeated headers and footers, filters decorative elements and page artifacts, skips table-of-contents pages, detects section headings using typographical features (e.g., font size and boldness), and rebuilds coherent page-level text while preserving document structure. This significantly improves text quality by addressing common PDF extraction challenges such as duplicated headings, broken reading order, and fragmented paragraphs.

The reconstructed pages are then processed into overlapping chunks of approximately 400 words with configurable overlap to preserve contextual continuity across chunk boundaries. Each chunk is enriched with metadata including the report identifier, company ticker, reporting year, source page range, section title, word count, estimated token count, and a SHA-256 content hash for deduplication and traceability. The processing logic is organised into modular components with dedicated responsibilities for PDF parsing (`pdf_reader.py`), page reconstruction (`page_builder.py`), chunk generation (`chunking.py`), orchestration (`service.py`), and data loading. Finally, **dlt** ingests the processed chunks into **PostgreSQL**, where they form a structured knowledge base that is optimized for downstream embedding generation, semantic retrieval using **pgvector**, and Retrieval-Augmented Generation (RAG). This pipeline solves the key challenges of converting heterogeneous, visually rich financial reports into coherent, searchable, and metadata-rich text suitable for large language model applications.

One pipeline extracts narrative text, while another extracts structured tables, because each requires different processing to preserve the information needed for downstream tasks. Initially stored as relational table, but it wasn't extracted well, so swicthed to json instaed. Switched to remove the tables in narrative chunks, to reduce redundancy. Two-column is not table and still captured by the narrative chunk.

Updated the postgres to include the pgvector extension

## Retrieval Index

The retrieval pipeline builds a unified search index from both the narrative content and structured tables extracted during ingestion. Narrative chunks from `report_chunks` and the text representation (`rag_text`) of extracted tables from `report_tables` are combined into a single `retrieval_documents` table. Each retrieval document stores its source metadata (e.g., report, company, year, pages, and content type), a PostgreSQL full-text search vector for keyword retrieval, and a dense embedding generated using a SentenceTransformer model for semantic retrieval. The original structured table JSON remains stored separately in `report_tables` and can be retrieved whenever a table document is selected.

## Search

The project supports three retrieval strategies over the same indexed corpus:

- **Keyword Search:** Uses PostgreSQL Full-Text Search (FTS) to retrieve documents based on lexical similarity, making it effective for exact financial terms and values.
- **Vector Search:** Uses dense embeddings stored with `pgvector` to retrieve semantically similar documents, allowing relevant information to be found even when the query wording differs from the source text.
- **Hybrid Search:** Combines keyword and vector retrieval using Reciprocal Rank Fusion (RRF), leveraging the strengths of both lexical and semantic search to improve overall retrieval quality.

Using a unified retrieval index enables narrative passages and financial tables to compete during retrieval. When a table document is returned, the application can use its `source_id` to retrieve the original structured JSON from `report_tables`, ensuring that downstream RAG components receive both high-quality retrieval results and the underlying structured financial data.

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

## Evaluation Framework

The project includes an evaluation framework for comparing the standard RAG pipeline with the agentic financial-analysis pipeline.

The framework evaluates:

- retrieval quality;
- answer correctness;
- faithfulness to retrieved evidence;
- answer relevance;
- latency;
- agent tool use and execution success.

---

## Benchmark Generation

Because no manually labelled ground-truth dataset was initially available, the evaluation benchmark is generated from the indexed annual-report corpus.

The benchmark generation pipeline is:

```text
Annual Report Corpus
        │
        ▼
Stratified Sampling
(Ticker × Report Year)
        │
        ▼
Financial Question Generation
        │
        ▼
Static Quality Checks
        │
        ▼
LLM Validation
        │
        ▼
Quality / Difficulty Thresholds
        │
        ▼
Benchmark Dataset
```

Documents are sampled across **ticker and reporting year** to reduce over-representation of a single company or period.

Generated examples are stored in:

```text
data/evaluation/benchmark.jsonl
```

### Benchmark Question Types

The benchmark focuses on sufficiently challenging financial-analysis tasks.

| Category | Description |
| --- | --- |
| **Financial Metric** | Retrieves financially meaningful values while preserving the correct entity, period, unit, and accounting context. |
| **Table Reasoning** | Requires reasoning across multiple rows, columns, periods, entities, or financial categories. |
| **Within-Source Comparison** | Compares financially related values contained within the same source. |
| **Cross-Report Comparison** | Compares the same financial metric across different reporting periods. |
| **Calculation** | Requires deterministic calculations such as percentage growth, absolute change, ratios, margins, and contribution percentages. |
| **Multi-Hop** | Requires combining evidence from multiple sources. |
| **Financial Interpretation** | Requires an objective financial conclusion supported by reported values. |

The default benchmark distribution is:

```text
Financial Metric              10%
Table Reasoning               15%
Within-Source Comparison      15%
Cross-Report Comparison       20%
Calculation                   20%
Multi-Hop                     15%
Financial Interpretation       5%
```

Most questions therefore require more than simple factual retrieval.

### Benchmark Validation

Each generated question-answer pair is automatically validated before inclusion.

The validator checks:

- financial relevance;
- grounding in annual-report evidence;
- question difficulty;
- currency and unit accuracy;
- reporting-period accuracy;
- Group, Company, subsidiary, segment, and geographic distinctions;
- calculation validity;
- compatibility of compared financial metrics;
- multi-source necessity;
- absence of parser or database artifacts;
- naturalness of the question.

Each benchmark example includes validation metadata such as:

```json
{
  "quality_score": 0.95,
  "difficulty_score": 0.90,
  "financial_relevance_score": 1.0,
  "human_verified": false
}
```

Examples that fail the configured thresholds are rejected.

Synthetic examples remain marked:

```text
human_verified = false
```

until manually reviewed. A final benchmark can therefore be human-validated and frozen before being treated as a gold evaluation dataset.

---

## Evaluation Architecture

The same benchmark can be used to evaluate both the RAG and agent pipelines.

```text
Benchmark Question
        │
        ├───────────────────────┐
        ▼                       ▼
      RAG                    Agent
        │                       │
        ▼                       ▼
Initial Retrieval         Initial Retrieval
        │                       │
        ▼                       ▼
Answer Generation         Gemini Agent
                                │
                                ├── Additional Retrieval
                                ├── Table Lookup
                                ├── Calculator
                                └── Other Tools
                                │
                                ▼
                             Answer
```

For the agent, the evaluator separately records the initial retrieval results and the final evidence accumulated through tool calls.

---

## Retrieval Metrics

### Precision@K

Measures the proportion of the top-K retrieved documents that are relevant.

```text
Precision@K =
Relevant documents retrieved in top K
-------------------------------------
K
```

### Recall@K

Measures the proportion of all relevant evidence retrieved within the top-K results.

```text
Recall@K =
Relevant documents retrieved in top K
-------------------------------------
Total relevant documents
```

### Hit Rate@K

Measures whether at least one relevant document appears in the top-K results.

For each question:

```text
Hit = 1  if at least one relevant document is in top K
Hit = 0  otherwise
```

The benchmark-level Hit Rate is the mean across all questions.

### Mean Reciprocal Rank (MRR)

Measures how highly the first relevant result appears.

For one query:

```text
Reciprocal Rank = 1 / rank of first relevant result
```

Examples:

```text
Rank 1 → 1.00
Rank 2 → 0.50
Rank 4 → 0.25
No relevant result → 0.00
```

The mean across all benchmark questions gives **MRR**.

### nDCG@K

Normalized Discounted Cumulative Gain rewards relevant documents appearing higher in the ranking and supports questions with multiple relevant sources.

---

## Answer Evaluation

### Token F1

Measures lexical overlap between the generated answer and reference answer.

Token F1 provides a deterministic baseline but is not sufficient by itself because financially equivalent answers may use different wording.

### Answer Correctness

An LLM judge compares the generated answer with the benchmark reference answer.

The judge checks:

- financial values;
- currencies;
- units;
- reporting periods;
- entity distinctions;
- completeness.

### Faithfulness

Measures whether factual claims in the generated answer are supported by the evidence retrieved by the pipeline.

This is evaluated separately from correctness. An answer may contain the correct fact but still receive a lower faithfulness score if the retrieved evidence does not support the claim.

### Answer Relevance

Measures whether the response directly and sufficiently answers the question without unnecessary or unrelated information.

### LLM Judge Explanations

The LLM judge returns both a score and a concise explanation for each metric.

```json
{
  "correctness": {
    "score": 1.0,
    "reason": "The values, units, and reporting periods match the reference answer."
  },
  "faithfulness": {
    "score": 0.9,
    "reason": "Most claims are supported by the retrieved evidence."
  },
  "relevance": {
    "score": 1.0,
    "reason": "The response directly answers the requested financial comparison."
  }
}
```

These explanations make individual evaluation failures easier to inspect.

---

## Agent-Specific Evaluation

The agent pipeline also records tool-related metrics.

| Metric | Description |
| --- | --- |
| **Tool Count** | Number of additional tools invoked by the agent. |
| **Tool Success Rate** | Proportion of invoked tools that execute successfully. |
| **Tool F1** | Compares selected tools with expected tools when tool annotations are available. |
| **Latency** | Total time required to complete the query. |

Tool-call traces are retained so the evaluation can inspect:

- which tools Gemini selected;
- the arguments sent to each tool;
- whether each tool succeeded;
- how additional retrieval affected the final evidence set.

---

## Initial vs Final Retrieval

For the agent pipeline, retrieval is evaluated at two stages.

```text
User Question
      │
      ▼
Initial Hybrid Retrieval
      │
      ├── Initial Precision@K
      ├── Initial Recall@K
      ├── Initial Hit Rate@K
      ├── Initial MRR
      └── Initial nDCG@K
      │
      ▼
Gemini Agent
      │
      ├── Keyword Search
      ├── Semantic Search
      ├── Hybrid Search
      ├── Table Lookup
      └── Other Tools
      │
      ▼
Final Evidence Set
      │
      ├── Final Precision@K
      ├── Final Recall@K
      ├── Final Hit Rate@K
      ├── Final MRR
      └── Final nDCG@K
      │
      ▼
Final Answer
```

This allows the evaluation to determine whether agentic retrieval improves evidence coverage beyond the initial RAG stage.

---

## Evaluation Output

Evaluation results are stored as Excel workbooks under:

```text
outputs/evaluation/
```

Example outputs:

```text
outputs/evaluation/
├── rag_keyword_evaluation.xlsx
├── rag_vector_evaluation.xlsx
├── rag_hybrid_evaluation.xlsx
└── agent_evaluation.xlsx
```

Each workbook contains three sheets.

### Summary

Contains averaged evaluation metrics such as:

- Precision@K;
- Recall@K;
- Hit Rate@K;
- MRR;
- nDCG@K;
- Token F1;
- Answer Correctness;
- Faithfulness;
- Answer Relevance;
- Latency;
- Tool Success Rate.

### Detailed Results

Contains one row per benchmark question, including:

- question;
- reference answer;
- generated answer;
- benchmark category;
- gold source IDs;
- retrieved source IDs;
- retrieval metrics;
- answer-quality scores;
- LLM judge explanations;
- tool calls;
- latency;
- errors.

### Errors

Contains benchmark examples that failed during:

- retrieval;
- answer generation;
- tool execution;
- LLM judging;
- evaluation processing.

---

### Metrics Summary

| Evaluation Dimension | Metric |
| --- | --- |
| Retrieval relevance | Precision@K |
| Evidence coverage | Recall@K |
| Retrieval success | Hit Rate@K |
| First relevant result ranking | MRR |
| Overall ranking quality | nDCG@K |
| Lexical answer similarity | Token F1 |
| Factual answer accuracy | Answer Correctness |
| Evidence grounding | Faithfulness |
| Question-answer alignment | Answer Relevance |
| Agent reliability | Tool Success Rate |
| Agent tool behavior | Tool Count / Tool F1 |
| Efficiency | Latency |

The framework therefore provides a consistent way to compare **keyword RAG, semantic RAG, hybrid RAG, and the agentic financial-analysis pipeline** using the same financially focused benchmark.
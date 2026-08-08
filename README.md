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




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

One pipeline extracts narrative text, while another extracts structured tables, because each requires different processing to preserve the information needed for downstream tasks. Initially stored as relational table, but it wasn't extracted well, so swicthed to json instaed

To Do: give me SQL to check if the tables are detected, then fix the noise




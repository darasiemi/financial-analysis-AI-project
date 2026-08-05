# Nigeria Stock Financial Analysis Project

## Introduction

This is a final project for the Data Talks Club LLM [Zoomcamp](https://datatalks.club/docs/courses/llm-zoomcamp/) . In this project, I have implemented the end-to-end

## Data Ingestion

The ingestion pipeline automatically downloads annual reports from selected Nigerian listed companies, validates each file (PDF integrity, report year, and duplicates), and stores them in a structured local directory for downstream processing. It uses `requests` for direct downloads, `Playwright` for JavaScript-protected sources, `PyMuPDF` for PDF validation, and SHA-256 hashing for file integrity. The downloaded reports serve as the primary data source for document parsing, embedding generation, and financial analysis.


The data ingestion pipeline processes downloaded annual reports and loads them into PostgreSQL using **dlt**. The pipeline extracts report metadata (company, report year, file path, checksum, page count) and page-level text using **PyMuPDF**, then stores the results in structured database tables (`reports` and `report_pages`). Each report undergoes validation for PDF integrity, report year, and text extraction quality, enabling reliable downstream processing for chunking, embedding generation, and retrieval-augmented financial analysis.


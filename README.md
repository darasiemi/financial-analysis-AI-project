# Nigeria Stock Financial Analysis Project

## Table of Contents

1. [Introduction](#introduction)
2. [Problem Statement](#problem-statement)
3. [Documentation](#documentation)
4. [Technology Stack](#technology-stack)
5. [Generative AI Use Declaration](#generative-ai-use-declaration)
6. [Acknowledgements](#acknowledgements)

## Introduction

This project is my final project for the DataTalks.Club [LLM Zoomcamp](https://github.com/DataTalksClub/llm-zoomcamp), an online bootcamp focused on building applications with Large Language Models (LLMs).

The LLM Zoomcamp is the **fourth DataTalks.Club Zoomcamp** I have taken, following the **Data Engineering Zoomcamp, Machine Learning Zoomcamp, and MLOps Zoomcamp**. Rather than treating the lessons from these programmes independently, I adapted relevant engineering practices from them to build this project as an end-to-end financial analysis LLM application.

The project applies concepts from the LLM Zoomcamp to build **RAG and agentic pipelines for analysing Nigerian companies' annual reports**. It also incorporates practices from the MLOps Zoomcamp and extends them to **LLMOps**, including:

- **Data pipelines** for ingesting, validating, processing, chunking, and storing financial reports and tables.
- **Retrieval infrastructure** combining keyword, semantic, and hybrid search with PostgreSQL and pgvector.
- **RAG and agentic pipelines** for grounded financial question answering, tool use, and source citation.
- **Evaluation pipelines** for generating benchmark datasets and evaluating retrieval and answer quality.
- **LLM observability** for tracking interactions, model calls, token usage, latency, and application costs.
- **Monitoring** with PostgreSQL and Grafana dashboards for application and LLM metrics.
- **Deployment** of the FastAPI backend, Streamlit frontend, and PostgreSQL database using Docker and Railway.
- **Testing and software quality** through smoke and integration tests, linting, formatting, pre-commit hooks, and reproducible Makefile commands.
- **Reproducible development environments and dependency management** using `uv` and Docker.
- **Production-to-local monitoring workflows** for analysing production telemetry locally in Grafana.

The result is not only an LLM application, but an attempt to apply the **end-to-end engineering lifecycle to LLM systems**: from data ingestion and retrieval to evaluation, deployment, monitoring, and continuous code-quality practices.

## Problem Statement

I started this project after recognising a gap in my own financial knowledge. I wanted to better understand how to evaluate companies, interpret financial reports, and make investment decisions based on analysis.

This is not an isolated challenge. Financial literacy remains a significant issue in Nigeria: research cited by the IMF found that **more than half of Nigerian adults have limited financial literacy and capability**, particularly in financial planning. The Central Bank of Nigeria similarly recognises that many Nigerians lack the skills required to effectively manage their finances and take advantage of financial products and opportunities.

Yet, making informed investment decisions often requires reading lengthy annual reports, comparing financial performance across years, identifying relevant metrics, and understanding the wider context behind the numbers.

**Financial Analysis AI** was built to make this process more accessible. It uses retrieval-augmented generation (RAG) and agentic workflows to analyse company annual reports, answer financial questions with supporting evidence, explore financial tables, and compare company performance.

The initial implementation focuses on **MTN Nigeria, Guaranty Trust Holding Company (GTCO), and Zenith Bank** as a starting point. However, the underlying ingestion, retrieval, and analysis architecture is designed to be extensible to other companies listed on the **Nigerian Exchange (NGX)**.

Ultimately, the goal is not to automate investment decisions, but to **improve financial literacy and support more informed, evidence-based investment analysis**.

![Demo](media/streamlit-app-video.webm)

<!-- ffmpeg -i media/streamlit-app-video.webm media/streamlit-app-video.gif -->
## Documentation

For more details about the project, see:

- **[Setup Guide](SETUP.md)** — Instructions for installing dependencies, configuring the environment, ingesting data, running the application, testing, evaluation, and monitoring.
- **[System Architecture](SYSTEM.md)** — A detailed description of the system architecture, including data ingestion, storage, retrieval, RAG and agent pipelines, deployment, and observability.

## Technology Stack

The project combines data engineering, retrieval, LLM application development, deployment, evaluation, and observability technologies.

| Area | Technologies | Purpose |
|---|---|---|
| **Programming Language** | Python | Core application, ingestion, retrieval, RAG, agent, evaluation, and monitoring logic |
| **Dependency Management** | `uv` | Python dependency and environment management |
| **Data Ingestion** | `requests`, Playwright | Downloading company annual reports |
| **PDF Processing** | PyMuPDF | Extracting and processing narrative content from annual reports |
| **Data Loading** | `dlt` | Loading processed financial-report data into PostgreSQL |
| **Database** | PostgreSQL | Storing report content, metadata, structured tables, and monitoring telemetry |
| **Vector Database** | pgvector | Storing embeddings and performing vector similarity search within PostgreSQL |
| **Embeddings** | SentenceTransformers | Generating embeddings for semantic retrieval |
| **Keyword Retrieval** | PostgreSQL Full-Text Search | Lexical search over financial-report content |
| **Hybrid Retrieval** | Reciprocal Rank Fusion (RRF) | Combining keyword and semantic search results |
| **LLM** | Gemini API | RAG answer generation, agent reasoning, and LLM-based evaluation |
| **RAG** | Custom Python pipeline | Evidence-grounded question answering over annual reports |
| **Agentic AI** | Gemini tool calling + custom tools | Financial analysis using retrieval, table lookup, calculation, web search, and presentation generation |
| **Backend** | FastAPI, Uvicorn | API layer and orchestration of RAG and agent pipelines |
| **Frontend** | Streamlit | Interactive financial analysis interface |
| **Evaluation** | Custom evaluation pipeline | Benchmark generation and retrieval/answer quality evaluation |
| **Monitoring & Observability** | Grafana, PostgreSQL | Monitoring latency, costs, token usage, relevance, feedback, and application behaviour |
| **Containerisation** | Docker, Docker Compose | Reproducible local database and monitoring services |
| **Deployment** | Railway | Production hosting for the FastAPI backend and PostgreSQL |
| **Testing** | pytest | Smoke and integration testing |
| **Code Quality** | Black, isort, Pylint | Formatting, import ordering, and static code analysis |
| **Development Automation** | GNU Make, pre-commit | Standardised development workflows and automated quality checks |
| **Notebooks** | Jupyter Notebook | Exploration and development analysis |
| **Version Control** | Git, GitHub | Source control and project hosting |

## Generative AI Use Declaration

Generative AI was used as a **development and learning aid** during the implementation of this project. I primarily interacted with AI through conversational chat interfaces to discuss implementation approaches, troubleshoot problems, clarify technical concepts, and generate or refine portions of code.

I **did not use autonomous or automated AI coding agents** to independently modify the repository or implement features on my behalf. Where AI-generated code was used, I manually copied and pasted it into the codebase. This kept the development process under my direct control and allowed me to review the generated code, understand how it fitted into the wider system, and make changes where necessary.

This workflow also meant that generated code did not automatically translate into working software. I encountered implementation errors, integration issues, unexpected behaviour, and bugs while running the code. I used these problems as opportunities to investigate the underlying behaviour, ask follow-up questions, consult relevant documentation where necessary, and develop a deeper understanding of the technologies and design decisions involved. All git commits and push were 100% made by me. 

AI assistance was used for activities including:

- discussing system architecture and implementation approaches;
- generating and refining code snippets;
- debugging errors and investigating unexpected behaviour;
- explaining unfamiliar libraries, APIs, algorithms, and engineering concepts;
- reviewing implementation choices and considering alternatives;
- developing and refining database, retrieval, RAG, agentic, evaluation, deployment, and monitoring components;
- improving technical documentation and code readability; and
- assisting with test design and interpretation of results.
- Generating and refining the system architecture diagram

I remained responsible for integrating and executing the code, configuring the development and deployment environments, validating system behaviour, and making the final technical and architectural decisions.

To support maintainability and code quality, I also established automated **formatting, linting, testing, and pre-commit checks** within the development workflow. These checks help identify formatting inconsistencies, code-quality issues.

## Acknowledgements

I would like to thank [DataTalks.Club](https://datatalks.club/) and its community for the excellent open learning resources they provide. Their courses have played an important role in developing my practical understanding of machine learning engineering and the end-to-end process of building production-oriented AI systems.

In particular, the hands-on and project-focused nature of the courses helped me connect concepts across data engineering, machine learning, LLM applications, deployment, testing, monitoring, and MLOps. Many of the engineering practices I applied while building this project were strengthened by what I learned through DataTalks.Club.



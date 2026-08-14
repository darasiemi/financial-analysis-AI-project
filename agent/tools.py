from __future__ import annotations

from typing import Any

import psycopg

from ingestion.processing.database import (
    get_postgres_connection_string,
    load_environment,
)
from retrieval.hybrid import hybrid_search
from retrieval.keyword import keyword_search
from retrieval.vector import vector_search


def _compact_results(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Convert retrieval results into a compact structure that is
    easy for the LLM to inspect.
    """

    documents = []

    for result in results:
        documents.append(
            {
                "source_id": result["source_id"],
                "content_type": result["content_type"],
                "ticker": result["ticker"],
                "report_year": result["report_year"],
                "page_start": result["page_start"],
                "page_end": result["page_end"],
                "section_title": result.get("section_title"),
                "text": result["text"],
            }
        )

    return {
        "count": len(documents),
        "documents": documents,
    }


def search_keyword(
    query: str,
    ticker: str | None = None,
    report_year: int | None = None,
    top_k: int = 8,
) -> dict[str, Any]:
    """
    Search annual reports using lexical keyword matching.

    Use this tool when the question contains exact terminology,
    names, job titles, accounting metrics, or phrases likely to
    appear directly in an annual report.

    Args:
        query:
            Search query.

        ticker:
            Optional company ticker such as GTCO or MTNN.

        report_year:
            Optional annual-report year.

        top_k:
            Maximum number of results.

    Returns:
        Ranked annual-report passages and tables.
    """

    results = keyword_search(
        query,
        top_k=top_k,
        ticker=ticker,
        report_year=report_year,
    )

    return _compact_results(results)


def search_semantic(
    query: str,
    ticker: str | None = None,
    report_year: int | None = None,
    top_k: int = 8,
) -> dict[str, Any]:
    """
    Search annual reports using semantic vector similarity.

    Use this when the user's wording may differ from the
    terminology used in the reports.

    Args:
        query:
            Semantic search query.

        ticker:
            Optional company ticker.

        report_year:
            Optional annual-report year.

        top_k:
            Maximum number of results.

    Returns:
        Semantically relevant annual-report passages and tables.
    """

    results = vector_search(
        query,
        top_k=top_k,
        ticker=ticker,
        report_year=report_year,
    )

    return _compact_results(results)


def search_hybrid(
    query: str,
    ticker: str | None = None,
    report_year: int | None = None,
    top_k: int = 8,
) -> dict[str, Any]:
    """
    Search annual reports using both lexical and semantic
    retrieval with Reciprocal Rank Fusion.

    Use this as the general-purpose retrieval tool when both
    exact terminology and semantic relevance may matter.

    Args:
        query:
            Search query.

        ticker:
            Optional company ticker.

        report_year:
            Optional report year.

        top_k:
            Maximum number of results.

    Returns:
        Ranked annual-report passages and tables.
    """

    results = hybrid_search(
        query,
        top_k=top_k,
        ticker=ticker,
        report_year=report_year,
    )

    return _compact_results(results)


def get_table(
    table_id: str,
) -> dict[str, Any]:
    """
    Fetch the original structured JSON for a table returned by
    retrieval.

    Use this after a search result has content_type='table' when
    exact rows, columns, financial values, or comparisons are
    needed.

    Args:
        table_id:
            source_id of a retrieved table.

    Returns:
        Table metadata and structured JSON.
    """

    load_environment()

    connection_string = get_postgres_connection_string()

    with psycopg.connect(connection_string) as connection:

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    table_id,
                    report_id,
                    ticker,
                    report_year,
                    pdf_page_number,
                    table_title,
                    table_data
                FROM financial_analysis.report_tables
                WHERE table_id = %s
                """,
                (table_id,),
            )

            row = cursor.fetchone()

    if row is None:
        return {"error": (f"Table '{table_id}' was not found.")}

    (
        table_id,
        report_id,
        ticker,
        report_year,
        page_number,
        title,
        table_data,
    ) = row

    return {
        "table_id": table_id,
        "report_id": report_id,
        "ticker": ticker,
        "report_year": report_year,
        "pdf_page_number": page_number,
        "table_title": title,
        "table_data": table_data,
    }

from __future__ import annotations

from typing import Any

import psycopg

from ingestion.processing.database import (
    get_postgres_connection_string,
    load_environment,
)


def get_available_filters() -> dict[str, list[Any]]:
    load_environment()

    connection_string = get_postgres_connection_string()

    query = """
        SELECT DISTINCT
            ticker,
            report_year
        FROM financial_analysis.retrieval_documents
        WHERE ticker IS NOT NULL
          AND report_year IS NOT NULL
        ORDER BY ticker, report_year
    """

    tickers: set[str] = set()
    years: set[int] = set()

    with psycopg.connect(connection_string) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)

            for ticker, report_year in cursor.fetchall():
                if ticker:
                    tickers.add(str(ticker))

                if report_year is not None:
                    years.add(int(report_year))

    return {
        "tickers": sorted(tickers),
        "years": sorted(years),
    }


def get_corpus_stats() -> dict[str, int]:
    load_environment()

    connection_string = get_postgres_connection_string()

    query = """
        SELECT
            COUNT(*) AS document_count,
            COUNT(DISTINCT ticker) AS ticker_count,
            COUNT(DISTINCT report_year) AS year_count,
            COUNT(*) FILTER (
                WHERE content_type = 'table'
            ) AS table_count,
            COUNT(*) FILTER (
                WHERE content_type = 'narrative'
            ) AS narrative_count
        FROM financial_analysis.retrieval_documents
    """

    with psycopg.connect(connection_string) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    if row is None:
        return {
            "documents": 0,
            "companies": 0,
            "years": 0,
            "tables": 0,
            "narratives": 0,
        }

    return {
        "documents": int(row[0] or 0),
        "companies": int(row[1] or 0),
        "years": int(row[2] or 0),
        "tables": int(row[3] or 0),
        "narratives": int(row[4] or 0),
    }


def database_is_available() -> bool:
    try:
        load_environment()

        connection_string = get_postgres_connection_string()

        with psycopg.connect(
            connection_string,
            connect_timeout=3,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

        return True

    except Exception:
        return False

from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

from ingestion.processing.config import (
    ENV_PATH,
    POSTGRES_SCHEMA,
    REPORTS_TABLE,
)
from ingestion.processing.models import ReportRecord


def load_environment() -> None:
    """Load environment variables from ingestion/.env."""

    if not ENV_PATH.exists():
        raise FileNotFoundError(f"Environment file not found: {ENV_PATH}")

    load_dotenv(ENV_PATH)


def get_postgres_connection_string() -> str:
    """
    Return the PostgreSQL connection string.

    dlt's full connection variable is used when available. Otherwise,
    the connection string is built from the individual PostgreSQL
    environment variables.
    """

    configured_url = os.getenv("DESTINATION__POSTGRES__CREDENTIALS")

    if configured_url:
        return configured_url

    database = os.getenv("POSTGRES_DB")
    username = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")

    missing = [
        name
        for name, value in {
            "POSTGRES_DB": database,
            "POSTGRES_USER": username,
            "POSTGRES_PASSWORD": password,
        }.items()
        if not value
    ]

    if missing:
        raise RuntimeError("Missing PostgreSQL configuration: " + ", ".join(missing))

    return f"postgresql://{username}:{password}" f"@{host}:{port}/{database}"


def load_reports(
    connection_string: str,
) -> list[ReportRecord]:
    """Load annual-report file metadata from PostgreSQL."""

    query = f"""
        SELECT
            report_id,
            ticker,
            report_year,
            file_path
        FROM {POSTGRES_SCHEMA}.{REPORTS_TABLE}
        ORDER BY ticker, report_year, filename;
    """

    reports: list[ReportRecord] = []

    with psycopg2.connect(connection_string) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query)

            for row in cursor:
                file_path = Path(str(row["file_path"]))

                if not file_path.exists():
                    raise FileNotFoundError(
                        "PDF referenced in PostgreSQL does not exist: " f"{file_path}"
                    )

                reports.append(
                    ReportRecord(
                        report_id=str(row["report_id"]),
                        ticker=str(row["ticker"]),
                        report_year=int(row["report_year"]),
                        file_path=file_path,
                    )
                )

    if not reports:
        raise RuntimeError(
            f"No reports found in " f"{POSTGRES_SCHEMA}.{REPORTS_TABLE}."
        )

    return reports

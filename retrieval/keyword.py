from __future__ import annotations

import psycopg

from ingestion.processing.config import (
    POSTGRES_SCHEMA,
    RETRIEVAL_DOCUMENTS_TABLE,
)
from ingestion.processing.database import (
    get_postgres_connection_string,
    load_environment,
)


def keyword_search(
    query: str,
    *,
    top_k: int = 10,
    ticker: str | None = None,
    report_year: int | None = None,
) -> list[dict]:
    """
    PostgreSQL full-text keyword retrieval.
    """

    load_environment()

    connection_string = get_postgres_connection_string()

    filters: list[str] = ["""
        search_vector
        @@ websearch_to_tsquery(
            'english',
            %s
        )
        """]

    parameters: list = [
        query,
    ]

    if ticker is not None:
        filters.append("ticker = %s")
        parameters.append(ticker)

    if report_year is not None:
        filters.append("report_year = %s")
        parameters.append(report_year)

    parameters.extend(
        [
            query,
            top_k,
        ]
    )

    where_clause = " AND ".join(filters)

    sql = f"""
        SELECT
            document_id,
            source_id,
            content_type,
            report_id,
            ticker,
            report_year,
            page_start,
            page_end,
            section_title,
            text,

            ts_rank_cd(
                search_vector,
                websearch_to_tsquery(
                    'english',
                    %s
                )
            ) AS score

        FROM
            {POSTGRES_SCHEMA}.{RETRIEVAL_DOCUMENTS_TABLE}

        WHERE
            {where_clause}

        ORDER BY
            score DESC

        LIMIT %s;
    """

    # Query is used once in WHERE and once for rank.
    # Reorder parameters accordingly.
    where_parameters = parameters[:-2]

    final_parameters = [
        query,
        *where_parameters,
        top_k,
    ]

    with psycopg.connect(connection_string) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                sql,
                final_parameters,
            )

            columns = [description.name for description in cursor.description]

            return [
                dict(
                    zip(
                        columns,
                        row,
                    )
                )
                for row in cursor.fetchall()
            ]

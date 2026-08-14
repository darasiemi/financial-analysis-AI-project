from __future__ import annotations

import psycopg
from pgvector.psycopg import (
    register_vector,
)
from sentence_transformers import (
    SentenceTransformer,
)

from ingestion.processing.config import (
    EMBEDDING_MODEL,
    POSTGRES_SCHEMA,
    RETRIEVAL_DOCUMENTS_TABLE,
)
from ingestion.processing.database import (
    get_postgres_connection_string,
    load_environment,
)

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _model  # pylint: disable=global-statement

    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)

    return _model


def vector_search(
    query: str,
    *,
    top_k: int = 10,
    ticker: str | None = None,
    report_year: int | None = None,
) -> list[dict]:
    """
    Semantic retrieval using cosine distance.
    """

    load_environment()

    model = get_embedding_model()

    query_embedding = model.encode(
        query,
        normalize_embeddings=True,
    )

    filters: list[str] = []

    filter_values: list = []

    if ticker is not None:
        filters.append("ticker = %s")
        filter_values.append(ticker)

    if report_year is not None:
        filters.append("report_year = %s")
        filter_values.append(report_year)

    where_clause = ""

    if filters:
        where_clause = "WHERE " + " AND ".join(filters)

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

            1 - (
                embedding
                <=> %s
            ) AS score

        FROM
            {POSTGRES_SCHEMA}.{RETRIEVAL_DOCUMENTS_TABLE}

        {where_clause}

        ORDER BY
            embedding <=> %s

        LIMIT %s;
    """

    parameters = [
        query_embedding,
        *filter_values,
        query_embedding,
        top_k,
    ]

    connection_string = get_postgres_connection_string()

    with psycopg.connect(connection_string) as connection:

        register_vector(connection)

        with connection.cursor() as cursor:

            cursor.execute(
                sql,
                parameters,
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

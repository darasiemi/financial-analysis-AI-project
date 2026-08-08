from __future__ import annotations

import logging
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

from ingestion.processing.config import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    POSTGRES_SCHEMA,
    RETRIEVAL_DOCUMENTS_TABLE,
)
from ingestion.processing.database import (
    get_postgres_connection_string,
    load_environment,
)


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger(__name__)


# ============================================================
# pgvector setup
# ============================================================


def ensure_vector_extension(
    connection: psycopg.Connection,
) -> None:
    """
    Ensure pgvector is enabled in the current PostgreSQL database.

    The Docker image makes the extension available, but PostgreSQL
    still requires CREATE EXTENSION inside each database.
    """

    logger.info(
        "Ensuring pgvector extension is enabled."
    )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE EXTENSION IF NOT EXISTS vector;
            """
        )

    connection.commit()


# ============================================================
# Retrieval table
# ============================================================


def create_retrieval_table(
    connection: psycopg.Connection,
) -> None:
    """
    Create the unified retrieval table.

    Narrative chunks and table representations are both indexed
    here so keyword, vector, and hybrid retrieval operate over the
    same corpus.
    """

    logger.info(
        "Ensuring retrieval table exists."
    )

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS
            {POSTGRES_SCHEMA}.{RETRIEVAL_DOCUMENTS_TABLE}
            (
                document_id TEXT PRIMARY KEY,

                source_id TEXT NOT NULL,

                content_type TEXT NOT NULL
                    CHECK (
                        content_type IN (
                            'narrative',
                            'table'
                        )
                    ),

                report_id TEXT NOT NULL,

                ticker TEXT NOT NULL,

                report_year INTEGER NOT NULL,

                page_start INTEGER NOT NULL,

                page_end INTEGER NOT NULL,

                section_title TEXT,

                text TEXT NOT NULL,

                search_vector TSVECTOR
                    GENERATED ALWAYS AS (
                        to_tsvector(
                            'english',
                            COALESCE(text, '')
                        )
                    ) STORED,

                embedding VECTOR(
                    {EMBEDDING_DIMENSION}
                )
            );
            """
        )

    connection.commit()


# ============================================================
# PostgreSQL indexes
# ============================================================


def create_indexes(
    connection: psycopg.Connection,
) -> None:
    """
    Create indexes used by keyword, metadata, and vector search.
    """

    logger.info(
        "Creating retrieval indexes."
    )

    with connection.cursor() as cursor:

        # ----------------------------------------------------
        # Full-text search
        # ----------------------------------------------------

        cursor.execute(
            f"""
            CREATE INDEX IF NOT EXISTS
            retrieval_documents_fts_idx
            ON
            {POSTGRES_SCHEMA}.{RETRIEVAL_DOCUMENTS_TABLE}
            USING GIN (
                search_vector
            );
            """
        )

        # ----------------------------------------------------
        # Metadata filtering
        # ----------------------------------------------------

        cursor.execute(
            f"""
            CREATE INDEX IF NOT EXISTS
            retrieval_documents_ticker_year_idx
            ON
            {POSTGRES_SCHEMA}.{RETRIEVAL_DOCUMENTS_TABLE}
            (
                ticker,
                report_year
            );
            """
        )

        cursor.execute(
            f"""
            CREATE INDEX IF NOT EXISTS
            retrieval_documents_content_type_idx
            ON
            {POSTGRES_SCHEMA}.{RETRIEVAL_DOCUMENTS_TABLE}
            (
                content_type
            );
            """
        )

    connection.commit()


# ============================================================
# Source loading
# ============================================================


def load_narrative_documents(
    connection: psycopg.Connection,
) -> list[dict[str, Any]]:
    """
    Convert report_chunks rows into retrieval documents.
    """

    logger.info(
        "Loading narrative chunks."
    )

    documents: list[
        dict[str, Any]
    ] = []

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                chunk_id,
                report_id,
                ticker,
                report_year,
                pdf_page_start,
                pdf_page_end,
                section_title,
                text
            FROM
                {POSTGRES_SCHEMA}.report_chunks
            WHERE
                text IS NOT NULL
                AND text <> ''
            ORDER BY
                report_id,
                chunk_index;
            """
        )

        for row in cursor.fetchall():

            (
                chunk_id,
                report_id,
                ticker,
                report_year,
                page_start,
                page_end,
                section_title,
                text,
            ) = row

            documents.append(
                {
                    "document_id": (
                        f"narrative:{chunk_id}"
                    ),
                    "source_id": chunk_id,
                    "content_type": (
                        "narrative"
                    ),
                    "report_id": report_id,
                    "ticker": ticker,
                    "report_year": (
                        report_year
                    ),
                    "page_start": (
                        page_start
                    ),
                    "page_end": (
                        page_end
                    ),
                    "section_title": (
                        section_title
                    ),
                    "text": text,
                }
            )

    logger.info(
        "Loaded %d narrative document(s).",
        len(documents),
    )

    return documents


def load_table_documents(
    connection: psycopg.Connection,
) -> list[dict[str, Any]]:
    """
    Convert report_tables.rag_text rows into retrieval documents.

    table_data remains stored separately as JSON/JSONB in
    report_tables and can be fetched later when a table result
    is selected by retrieval.
    """

    logger.info(
        "Loading table documents."
    )

    documents: list[
        dict[str, Any]
    ] = []

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                table_id,
                report_id,
                ticker,
                report_year,
                pdf_page_number,
                table_title,
                rag_text
            FROM
                {POSTGRES_SCHEMA}.report_tables
            WHERE
                rag_text IS NOT NULL
                AND rag_text <> ''
            ORDER BY
                report_id,
                pdf_page_number,
                table_index;
            """
        )

        for row in cursor.fetchall():

            (
                table_id,
                report_id,
                ticker,
                report_year,
                page_number,
                table_title,
                rag_text,
            ) = row

            documents.append(
                {
                    "document_id": (
                        f"table:{table_id}"
                    ),
                    "source_id": (
                        table_id
                    ),
                    "content_type": (
                        "table"
                    ),
                    "report_id": (
                        report_id
                    ),
                    "ticker": (
                        ticker
                    ),
                    "report_year": (
                        report_year
                    ),
                    "page_start": (
                        page_number
                    ),
                    "page_end": (
                        page_number
                    ),
                    "section_title": (
                        table_title
                    ),
                    "text": (
                        rag_text
                    ),
                }
            )

    logger.info(
        "Loaded %d table document(s).",
        len(documents),
    )

    return documents


def load_source_documents(
    connection: psycopg.Connection,
) -> list[dict[str, Any]]:
    """
    Load all content that should participate in retrieval.
    """

    narrative_documents = (
        load_narrative_documents(
            connection
        )
    )

    table_documents = (
        load_table_documents(
            connection
        )
    )

    documents = (
        narrative_documents
        + table_documents
    )

    logger.info(
        (
            "Loaded %d total retrieval document(s): "
            "%d narrative, %d tables."
        ),
        len(documents),
        len(narrative_documents),
        len(table_documents),
    )

    return documents


# ============================================================
# Embedding model
# ============================================================


def load_embedding_model() -> SentenceTransformer:
    """
    Load the configured SentenceTransformer embedding model.
    """

    logger.info(
        "Loading embedding model: %s",
        EMBEDDING_MODEL,
    )

    model = SentenceTransformer(
        EMBEDDING_MODEL
    )

    logger.info(
        "Embedding model loaded."
    )

    return model


def embed_documents(
    documents: list[dict[str, Any]],
    model: SentenceTransformer,
):
    """
    Generate normalized embeddings for all retrieval documents.
    """

    if not documents:
        raise ValueError(
            "No documents available for embedding."
        )

    texts = [
        document["text"]
        for document in documents
    ]

    logger.info(
        "Embedding %d document(s).",
        len(texts),
    )

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    if (
        len(embeddings)
        != len(documents)
    ):
        raise RuntimeError(
            (
                "Embedding count does not match "
                "document count."
            )
        )

    logger.info(
        "Generated %d embedding(s).",
        len(embeddings),
    )

    return embeddings


# ============================================================
# Loading retrieval documents
# ============================================================


def replace_retrieval_documents(
    connection: psycopg.Connection,
    documents: list[dict[str, Any]],
    embeddings,
) -> None:
    """
    Replace the current retrieval index with freshly generated
    documents and embeddings.
    """

    logger.info(
        "Replacing retrieval documents."
    )

    with connection.cursor() as cursor:

        cursor.execute(
            f"""
            TRUNCATE TABLE
                {POSTGRES_SCHEMA}.{RETRIEVAL_DOCUMENTS_TABLE};
            """
        )

        for (
            document,
            embedding,
        ) in zip(
            documents,
            embeddings,
        ):

            cursor.execute(
                f"""
                INSERT INTO
                    {POSTGRES_SCHEMA}.{RETRIEVAL_DOCUMENTS_TABLE}
                (
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
                    embedding
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                );
                """,
                (
                    document[
                        "document_id"
                    ],
                    document[
                        "source_id"
                    ],
                    document[
                        "content_type"
                    ],
                    document[
                        "report_id"
                    ],
                    document[
                        "ticker"
                    ],
                    document[
                        "report_year"
                    ],
                    document[
                        "page_start"
                    ],
                    document[
                        "page_end"
                    ],
                    document[
                        "section_title"
                    ],
                    document[
                        "text"
                    ],
                    embedding,
                ),
            )

    connection.commit()

    logger.info(
        "Retrieval documents loaded."
    )


# ============================================================
# Validation
# ============================================================


def validate_index(
    connection: psycopg.Connection,
) -> None:
    """
    Perform basic validation after indexing.
    """

    with connection.cursor() as cursor:

        cursor.execute(
            f"""
            SELECT
                content_type,
                COUNT(*)
            FROM
                {POSTGRES_SCHEMA}.{RETRIEVAL_DOCUMENTS_TABLE}
            GROUP BY
                content_type
            ORDER BY
                content_type;
            """
        )

        rows = cursor.fetchall()

        logger.info(
            "Indexed document counts:"
        )

        for (
            content_type,
            count,
        ) in rows:

            logger.info(
                "  %s: %d",
                content_type,
                count,
            )

        cursor.execute(
            f"""
            SELECT
                COUNT(*)
            FROM
                {POSTGRES_SCHEMA}.{RETRIEVAL_DOCUMENTS_TABLE}
            WHERE
                embedding IS NULL;
            """
        )

        missing_embeddings = (
            cursor.fetchone()[0]
        )

        if missing_embeddings:

            raise RuntimeError(
                (
                    f"{missing_embeddings} retrieval "
                    "document(s) have NULL embeddings."
                )
            )

        cursor.execute(
            f"""
            SELECT
                COUNT(*)
            FROM
                {POSTGRES_SCHEMA}.{RETRIEVAL_DOCUMENTS_TABLE};
            """
        )

        total_documents = (
            cursor.fetchone()[0]
        )

        logger.info(
            "Total indexed documents: %d",
            total_documents,
        )


# ============================================================
# Main
# ============================================================


def main() -> None:
    """
    Build the unified keyword + vector retrieval index.

    Sequence:

        1. Load environment
        2. Connect to PostgreSQL
        3. Enable pgvector
        4. Register vector type with psycopg
        5. Create retrieval table
        6. Read narrative chunks and table representations
        7. Generate embeddings
        8. Replace retrieval documents
        9. Create search indexes
       10. Validate
    """

    load_environment()

    connection_string = (
        get_postgres_connection_string()
    )

    logger.info(
        "Connecting to PostgreSQL."
    )

    with psycopg.connect(
        connection_string
    ) as connection:

        # ----------------------------------------------------
        # Critical ordering:
        #
        # PostgreSQL must know about the vector type before
        # pgvector's psycopg adapter can register it.
        # ----------------------------------------------------

        ensure_vector_extension(
            connection
        )

        register_vector(
            connection
        )

        logger.info(
            "pgvector registered with psycopg."
        )

        # ----------------------------------------------------
        # Database schema
        # ----------------------------------------------------

        create_retrieval_table(
            connection
        )

        # ----------------------------------------------------
        # Load retrieval corpus
        # ----------------------------------------------------

        documents = (
            load_source_documents(
                connection
            )
        )

        if not documents:
            raise RuntimeError(
                (
                    "No retrieval documents were found. "
                    "Run the ingestion pipelines first."
                )
            )

        # ----------------------------------------------------
        # Embeddings
        # ----------------------------------------------------

        model = (
            load_embedding_model()
        )

        embeddings = (
            embed_documents(
                documents,
                model,
            )
        )

        # ----------------------------------------------------
        # Load index
        # ----------------------------------------------------

        replace_retrieval_documents(
            connection,
            documents,
            embeddings,
        )

        # ----------------------------------------------------
        # Search indexes
        # ----------------------------------------------------

        create_indexes(
            connection
        )

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        validate_index(
            connection
        )

    logger.info(
        "Retrieval index successfully built."
    )


if __name__ == "__main__":
    main()
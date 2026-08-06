from __future__ import annotations

import logging

import dlt

from ingestion.pipelines.chunk_resources import (
    report_chunks_resource,
)
from ingestion.processing.config import (
    DATASET_NAME,
    PIPELINE_NAME,
)
from ingestion.processing.database import (
    get_postgres_connection_string,
    load_environment,
    load_reports,
)
from ingestion.processing.service import (
    process_all_reports,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Process the PDFs and load chunks into PostgreSQL."""

    load_environment()

    connection_string = (
        get_postgres_connection_string()
    )

    reports = load_reports(
        connection_string
    )

    logger.info(
        "Loaded metadata for %d PDF files.",
        len(reports),
    )

    chunks = process_all_reports(
        reports
    )

    if not chunks:
        raise RuntimeError(
            "No chunks were produced."
        )

    table_count = sum(
        bool(chunk["contains_table"])
        for chunk in chunks
    )

    logger.info(
        "Produced %d chunks; %d contain "
        "probable table content.",
        len(chunks),
        table_count,
    )

    pipeline = dlt.pipeline(
        pipeline_name=PIPELINE_NAME,
        destination=(
            dlt.destinations.postgres(
                connection_string
            )
        ),
        dataset_name=DATASET_NAME,
    )

    load_info = pipeline.run(
        report_chunks_resource(chunks)
    )

    print(load_info)

    logger.info(
        "Loaded chunks into "
        "%s.report_chunks.",
        DATASET_NAME,
    )


if __name__ == "__main__":
    main()
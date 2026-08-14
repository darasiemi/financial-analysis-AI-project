from __future__ import annotations

import logging

import dlt

from ingestion.pipelines.table_resources import (
    extracted_tables_resource,
)
from ingestion.processing.config import (
    DATASET_NAME,
    EXTRACTED_TABLES_TABLE,
)
from ingestion.processing.database import (
    get_postgres_connection_string,
    load_environment,
    load_reports,
)
from ingestion.processing.table_extractor import (
    extract_tables_from_all_reports,
)

logging.basicConfig(
    level=logging.INFO,
    format=("%(asctime)s | " "%(levelname)s | " "%(message)s"),
)

logger = logging.getLogger(__name__)


TABLE_PIPELINE_NAME = "financial_report_tables_pipeline"


def main() -> None:

    load_environment()

    connection_string = get_postgres_connection_string()

    reports = load_reports(connection_string)

    logger.info(
        "Loaded metadata for %d report file(s).",
        len(reports),
    )

    tables = extract_tables_from_all_reports(reports)

    logger.info(
        "Extracted %d table(s).",
        len(tables),
    )

    if not tables:

        raise RuntimeError("No tables were detected.")

    pipeline = dlt.pipeline(
        pipeline_name=(TABLE_PIPELINE_NAME),
        destination=(dlt.destinations.postgres(connection_string)),
        dataset_name=(DATASET_NAME),
    )

    load_info = pipeline.run(extracted_tables_resource(tables))

    print(load_info)

    logger.info(
        "Loaded extracted tables into " "%s.%s.",
        DATASET_NAME,
        EXTRACTED_TABLES_TABLE,
    )


if __name__ == "__main__":
    main()

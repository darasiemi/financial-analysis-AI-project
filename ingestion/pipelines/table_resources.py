from __future__ import annotations

from collections.abc import Iterator

import dlt

from ingestion.processing.config import (
    EXTRACTED_TABLES_TABLE,
)


@dlt.resource(
    name=EXTRACTED_TABLES_TABLE,
    write_disposition="replace",
    primary_key="table_id",
    columns={
        "table_data": {
            "data_type": "json",
        }
    },
)
def extracted_tables_resource(
    tables: list[dict],
) -> Iterator[dict]:
    """
    One record per structured table extracted from an annual-report PDF.

    table_data is stored as JSON instead of being normalized into
    child tables by dlt.
    """

    yield from tables
from __future__ import annotations

from collections.abc import Iterator

import dlt


@dlt.resource(
    name="report_chunks",
    write_disposition="replace",
    primary_key="chunk_id",
)
def report_chunks_resource(
    chunks: list[dict],
) -> Iterator[dict]:
    """Expose processed chunks as a dlt resource."""

    yield from chunks
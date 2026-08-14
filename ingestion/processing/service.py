from __future__ import annotations

import logging
import re

from ingestion.processing.chunking import (
    chunk_document_pages,
)
from ingestion.processing.debug import (
    write_chunks,
    write_processed_pages,
    write_raw_blocks,
)
from ingestion.processing.models import (
    ReportRecord,
)
from ingestion.processing.page_builder import (
    reconstruct_document_pages,
)
from ingestion.processing.pdf_reader import (
    read_pdf_blocks,
)

logger = logging.getLogger(__name__)


def normalize_for_deduplication(
    text: str,
) -> str:
    """
    Normalise chunk text before duplicate comparison.

    Differences in case, whitespace and punctuation are ignored.
    """

    text = text.lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    text = re.sub(
        r"[^\w\s]",
        "",
        text,
    )

    return text.strip()


def remove_duplicate_chunks(
    chunks: list[dict],
) -> list[dict]:
    """
    Remove exact semantic duplicates after normalisation.
    """

    unique: list[dict] = []

    seen: set[str] = set()

    for chunk in chunks:
        normalized = normalize_for_deduplication(chunk["text"])

        if not normalized:
            logger.warning(
                "Skipping empty normalized chunk: %s",
                chunk["chunk_id"],
            )
            continue

        if normalized in seen:
            logger.warning(
                "Skipping duplicate chunk: %s",
                chunk["chunk_id"],
            )
            continue

        seen.add(normalized)

        unique.append(chunk)

    # Reindex after duplicate removal.
    for index, chunk in enumerate(
        unique,
        start=1,
    ):
        chunk["chunk_index"] = index

    return unique


def process_report(
    report: ReportRecord,
) -> list[dict]:
    """
    Process one annual report:

    PDF
        -> raw blocks
        -> reconstructed pages
        -> paragraphs
        -> chunks
        -> deduplication
    """

    # --------------------------------------------------------
    # Stage 1: PDF extraction
    # --------------------------------------------------------

    raw_pages = read_pdf_blocks(str(report.file_path))

    write_raw_blocks(
        report,
        raw_pages,
    )

    # --------------------------------------------------------
    # Stage 2: Layout + paragraph reconstruction
    # --------------------------------------------------------

    processed_pages = reconstruct_document_pages(raw_pages)

    write_processed_pages(
        report,
        processed_pages,
    )

    # --------------------------------------------------------
    # Stage 3: Paragraph-aware chunking
    # --------------------------------------------------------

    chunks = chunk_document_pages(
        report_id=(report.report_id),
        ticker=(report.ticker),
        report_year=(report.report_year),
        pages=processed_pages,
    )

    before_deduplication = len(chunks)

    # --------------------------------------------------------
    # Stage 4: Deduplication
    # --------------------------------------------------------

    chunks = remove_duplicate_chunks(chunks)

    # --------------------------------------------------------
    # Stage 5: Debug final chunks
    # --------------------------------------------------------

    write_chunks(
        report,
        chunks,
    )

    logger.info(
        "%s: %d PDF pages → "
        "%d reconstructed pages → "
        "%d chunks "
        "(%d duplicate chunks removed)",
        report.report_id,
        len(raw_pages),
        len(processed_pages),
        len(chunks),
        (before_deduplication - len(chunks)),
    )

    return chunks


def process_all_reports(
    reports: list[ReportRecord],
) -> list[dict]:
    """
    Process every report.
    """

    all_chunks: list[dict] = []

    seen_hashes: set[tuple[str, str]] = set()

    for report in reports:
        chunks = process_report(report)

        for chunk in chunks:
            duplicate_key = (
                report.report_id,
                chunk["text_sha256"],
            )

            if duplicate_key in seen_hashes:
                logger.warning(
                    "Skipping duplicate hash: %s",
                    chunk["chunk_id"],
                )

                continue

            seen_hashes.add(duplicate_key)

            all_chunks.append(chunk)

    return all_chunks

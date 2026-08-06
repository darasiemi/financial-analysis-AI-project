from __future__ import annotations

import logging
import re

from ingestion.processing.chunking import (
    chunk_document_pages,
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
    text = re.sub(r"\s+", " ", text)
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
        normalized = normalize_for_deduplication(
            chunk["text"]
        )

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

    # Reindex chunks after duplicate removal.
    for index, chunk in enumerate(
        unique,
        start=1,
    ):
        chunk["chunk_index"] = index

    return unique


def process_report(
    report: ReportRecord,
) -> list[dict]:
    """Process one annual report from PDF to cleaned chunks."""

    raw_pages = read_pdf_blocks(
        str(report.file_path)
    )

    processed_pages = (
        reconstruct_document_pages(
            raw_pages
        )
    )

    chunks = chunk_document_pages(
        report_id=report.report_id,
        ticker=report.ticker,
        report_year=report.report_year,
        pages=processed_pages,
    )

    before_deduplication = len(chunks)

    chunks = remove_duplicate_chunks(
        chunks
    )

    logger.info(
        "%s: %d PDF pages → %d reconstructed pages "
        "→ %d chunks (%d duplicate chunks removed)",
        report.report_id,
        len(raw_pages),
        len(processed_pages),
        len(chunks),
        before_deduplication - len(chunks),
    )

    return chunks


def process_all_reports(
    reports: list[ReportRecord],
) -> list[dict]:
    """Process all reports and remove report-level duplicates."""

    all_chunks: list[dict] = []

    # Separate duplicate tracking by report.
    seen_hashes: set[
        tuple[str, str]
    ] = set()

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

            seen_hashes.add(
                duplicate_key
            )

            all_chunks.append(chunk)

    return all_chunks
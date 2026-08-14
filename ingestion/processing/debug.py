from __future__ import annotations

from pathlib import Path

from ingestion.processing.config import (
    DEBUG_DIR,
    DEBUG_PROCESSING,
)
from ingestion.processing.models import (
    ProcessedPage,
    RawBlock,
    ReportRecord,
)


def _report_debug_dir(
    report: ReportRecord,
) -> Path:
    directory = DEBUG_DIR / report.ticker / str(report.report_year) / report.report_id

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


def write_raw_blocks(
    report: ReportRecord,
    pages: list[list[RawBlock]],
) -> None:
    """
    Write the raw ordered PyMuPDF blocks to disk.

    This lets us determine whether an error already existed during
    extraction or was introduced by later reconstruction.
    """

    if not DEBUG_PROCESSING:
        return

    directory = _report_debug_dir(report) / "raw_blocks"

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    for page_index, blocks in enumerate(
        pages,
        start=1,
    ):
        path = directory / (f"page_{page_index:04d}.txt")

        parts: list[str] = []

        for block in blocks:
            parts.append(
                "\n".join(
                    [
                        "=" * 80,
                        (
                            f"BLOCK {block.block_index} | "
                            f"x0={block.x0:.1f} "
                            f"y0={block.y0:.1f} "
                            f"x1={block.x1:.1f} "
                            f"y1={block.y1:.1f}"
                        ),
                        (
                            f"font={block.median_font_size:.2f} | "
                            f"max_font={block.max_font_size:.2f} | "
                            f"bold={block.is_bold}"
                        ),
                        "-" * 80,
                        block.text,
                    ]
                )
            )

        path.write_text(
            "\n\n".join(parts),
            encoding="utf-8",
        )


def write_processed_pages(
    report: ReportRecord,
    pages: list[ProcessedPage],
) -> None:
    """
    Save reconstructed page paragraphs.
    """

    if not DEBUG_PROCESSING:
        return

    directory = _report_debug_dir(report) / "reconstructed_pages"

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    for page in pages:
        path = directory / (f"page_{page.page_number:04d}.txt")

        parts = [
            f"PAGE: {page.page_number}",
            f"SECTION: {page.section_title}",
            f"CONTAINS TABLE: {page.contains_table}",
            "=" * 80,
        ]

        for index, paragraph in enumerate(
            page.paragraphs,
            start=1,
        ):
            parts.extend(
                [
                    "",
                    f"[PARAGRAPH {index}]",
                    paragraph,
                ]
            )

        path.write_text(
            "\n".join(parts),
            encoding="utf-8",
        )


def write_chunks(
    report: ReportRecord,
    chunks: list[dict],
) -> None:
    """
    Save final chunks exactly as they will be loaded into PostgreSQL.
    """

    if not DEBUG_PROCESSING:
        return

    directory = _report_debug_dir(report) / "chunks"

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    for chunk in chunks:
        path = directory / (f"chunk_{chunk['chunk_index']:05d}.txt")

        content = "\n".join(
            [
                f"CHUNK ID: {chunk['chunk_id']}",
                f"TICKER: {chunk['ticker']}",
                f"YEAR: {chunk['report_year']}",
                f"SECTION: {chunk['section_title']}",
                (
                    "PDF PAGES: "
                    f"{chunk['pdf_page_start']}"
                    "-"
                    f"{chunk['pdf_page_end']}"
                ),
                f"WORDS: {chunk['word_count']}",
                f"PARAGRAPHS: {chunk['paragraph_count']}",
                "=" * 80,
                "",
                chunk["text"],
            ]
        )

        path.write_text(
            content,
            encoding="utf-8",
        )

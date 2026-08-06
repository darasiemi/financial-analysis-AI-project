from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass

from ingestion.processing.config import (
    MIN_CHUNK_WORDS,
    OVERLAP_WORDS,
    TARGET_WORDS,
)
from ingestion.processing.models import (
    ProcessedPage,
)


@dataclass(frozen=True)
class ParagraphUnit:
    text: str
    page_number: int
    section_title: str | None
    contains_table: bool


def estimate_token_count(text: str) -> int:
    """Estimate tokens using approximately four characters/token."""

    return max(
        1,
        math.ceil(len(text) / 4),
    )


def make_chunk_id(
    report_id: str,
    chunk_index: int,
    text: str,
) -> str:
    """Create a stable chunk identifier."""

    content_hash = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()[:16]

    return (
        f"{report_id}_chunk_"
        f"{chunk_index:05d}_"
        f"{content_hash}"
    )


def split_long_paragraph(
    paragraph: ParagraphUnit,
) -> list[ParagraphUnit]:
    """
    Split a paragraph only when it exceeds the target chunk size.
    """

    words = paragraph.text.split()

    if len(words) <= TARGET_WORDS:
        return [paragraph]

    sentences = [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+",
            paragraph.text,
        )
        if sentence.strip()
    ]

    if len(sentences) <= 1:
        return [
            ParagraphUnit(
                text=" ".join(
                    words[
                        index:
                        index + TARGET_WORDS
                    ]
                ),
                page_number=paragraph.page_number,
                section_title=paragraph.section_title,
                contains_table=paragraph.contains_table,
            )
            for index in range(
                0,
                len(words),
                TARGET_WORDS,
            )
        ]

    output: list[ParagraphUnit] = []
    current_sentences: list[str] = []
    current_words = 0

    for sentence in sentences:
        sentence_words = len(
            sentence.split()
        )

        if (
            current_sentences
            and current_words
            + sentence_words
            > TARGET_WORDS
        ):
            output.append(
                ParagraphUnit(
                    text=" ".join(
                        current_sentences
                    ),
                    page_number=paragraph.page_number,
                    section_title=paragraph.section_title,
                    contains_table=paragraph.contains_table,
                )
            )

            current_sentences = []
            current_words = 0

        current_sentences.append(sentence)
        current_words += sentence_words

    if current_sentences:
        output.append(
            ParagraphUnit(
                text=" ".join(
                    current_sentences
                ),
                page_number=paragraph.page_number,
                section_title=paragraph.section_title,
                contains_table=paragraph.contains_table,
            )
        )

    return output


def pages_to_paragraph_units(
    pages: list[ProcessedPage],
) -> list[ParagraphUnit]:
    """Flatten processed pages into ordered paragraph units."""

    units: list[ParagraphUnit] = []

    for page in pages:
        for paragraph in page.paragraphs:
            unit = ParagraphUnit(
                text=paragraph,
                page_number=page.page_number,
                section_title=page.section_title,
                contains_table=page.contains_table,
            )

            units.extend(
                split_long_paragraph(unit)
            )

    return units


def make_chunk_record(
    *,
    report_id: str,
    ticker: str,
    report_year: int,
    chunk_index: int,
    paragraphs: list[ParagraphUnit],
) -> dict:
    """Build one database-ready chunk record."""

    text = "\n\n".join(
        paragraph.text.strip()
        for paragraph in paragraphs
        if paragraph.text.strip()
    ).strip()

    word_count = len(text.split())

    table_words = sum(
        len(paragraph.text.split())
        for paragraph in paragraphs
        if paragraph.contains_table
    )

    table_word_ratio = (
        table_words / word_count
        if word_count
        else 0.0
    )

    pages = [
        paragraph.page_number
        for paragraph in paragraphs
    ]

    section_title = next(
        (
            paragraph.section_title
            for paragraph in reversed(
                paragraphs
            )
            if paragraph.section_title
        ),
        None,
    )

    return {
        "chunk_id": make_chunk_id(
            report_id,
            chunk_index,
            text,
        ),
        "report_id": report_id,
        "ticker": ticker,
        "report_year": report_year,
        "chunk_index": chunk_index,
        "section_title": section_title,
        "pdf_page_start": min(pages),
        "pdf_page_end": max(pages),
        "contains_table": (
            table_word_ratio >= 0.40
        ),
        "table_word_ratio": round(
            table_word_ratio,
            4,
        ),
        "text": text,
        "character_count": len(text),
        "word_count": word_count,
        "estimated_token_count": (
            estimate_token_count(text)
        ),
        "paragraph_count": len(
            paragraphs
        ),
        "text_sha256": hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest(),
    }


def select_overlap_paragraphs(
    paragraphs: list[ParagraphUnit],
) -> list[ParagraphUnit]:
    """Select complete trailing paragraphs for chunk overlap."""

    selected: list[ParagraphUnit] = []
    selected_words = 0

    for paragraph in reversed(paragraphs):
        selected.insert(0, paragraph)

        selected_words += len(
            paragraph.text.split()
        )

        if selected_words >= OVERLAP_WORDS:
            break

    return selected


def chunk_document_pages(
    *,
    report_id: str,
    ticker: str,
    report_year: int,
    pages: list[ProcessedPage],
) -> list[dict]:
    """
    Build chunks from complete paragraphs.

    Paragraphs are accumulated up to TARGET_WORDS. Paragraphs are
    split internally only when one paragraph exceeds the target.
    """

    units = pages_to_paragraph_units(pages)

    chunks: list[dict] = []
    current: list[ParagraphUnit] = []
    current_word_count = 0

    def flush_current() -> None:
        if not current:
            return

        total_words = sum(
            len(paragraph.text.split())
            for paragraph in current
        )

        if total_words < MIN_CHUNK_WORDS:
            return

        chunks.append(
            make_chunk_record(
                report_id=report_id,
                ticker=ticker,
                report_year=report_year,
                chunk_index=len(chunks) + 1,
                paragraphs=current,
            )
        )

    for unit in units:
        unit_word_count = len(
            unit.text.split()
        )

        current_section = next(
            (
                paragraph.section_title
                for paragraph in reversed(
                    current
                )
                if paragraph.section_title
            ),
            None,
        )

        section_changed = (
            bool(current)
            and current_section is not None
            and unit.section_title is not None
            and unit.section_title
            != current_section
        )

        would_exceed_target = (
            bool(current)
            and current_word_count
            + unit_word_count
            > TARGET_WORDS
        )

        if (
            section_changed
            or would_exceed_target
        ):
            previous = list(current)

            flush_current()

            current = select_overlap_paragraphs(
                previous
            )

            current_word_count = sum(
                len(paragraph.text.split())
                for paragraph in current
            )

            while (
                current
                and current_word_count
                + unit_word_count
                > TARGET_WORDS
            ):
                removed = current.pop(0)

                current_word_count -= len(
                    removed.text.split()
                )

        current.append(unit)
        current_word_count += unit_word_count

    if current:
        total_words = sum(
            len(paragraph.text.split())
            for paragraph in current
        )

        if total_words >= MIN_CHUNK_WORDS:
            flush_current()

        elif chunks:
            previous_chunk = chunks.pop()

            previous_unit = ParagraphUnit(
                text=previous_chunk["text"],
                page_number=previous_chunk[
                    "pdf_page_start"
                ],
                section_title=previous_chunk[
                    "section_title"
                ],
                contains_table=bool(
                    previous_chunk[
                        "contains_table"
                    ]
                ),
            )

            chunks.append(
                make_chunk_record(
                    report_id=report_id,
                    ticker=ticker,
                    report_year=report_year,
                    chunk_index=previous_chunk[
                        "chunk_index"
                    ],
                    paragraphs=[
                        previous_unit,
                        *current,
                    ],
                )
            )

    return chunks
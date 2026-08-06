from __future__ import annotations

import re
from collections import Counter
from math import ceil
from statistics import median

import pymupdf

from ingestion.processing.config import (
    BOTTOM_MARGIN_RATIO,
    MIN_REPEATED_MARGIN_PAGES,
    REPEATED_MARGIN_RATIO,
    TOP_MARGIN_RATIO,
)
from ingestion.processing.models import RawBlock


BOLD_FONT_TERMS = (
    "bold",
    "semibold",
    "demibold",
    "black",
    "heavy",
)


def clean_raw_text(value: str) -> str:
    """
    Perform conservative cleanup while preserving meaningful
    line boundaries.
    """

    value = value.replace("\u00a0", " ")
    value = value.replace("\u00ad", "")
    value = value.replace("￾", "")

    # Join words split across PDF line boundaries.
    value = re.sub(
        r"(?<=\w)-\s*\n\s*(?=\w)",
        "",
        value,
    )

    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)

    return value.strip()


def remove_layout_artifacts(text: str) -> str:
    """
    Remove border characters and layout fragments that may be
    represented as text objects inside a PDF.

    Examples removed:
        |
        +
        | + |
        ----------------
        ========
    """

    cleaned_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        # Lines containing only border and separator characters.
        if re.fullmatch(
            r"[\s|+_=—–\-]+",
            line,
        ):
            continue

        # One or two isolated table-border symbols.
        if re.fullmatch(
            r"[|+]{1,2}",
            line,
        ):
            continue

        # Combinations such as "| + |".
        if re.fullmatch(
            r"[|+\s]+",
            line,
        ):
            continue

        # Lines with very little useful alphabetic content and which
        # are dominated by border characters.
        alphabetic_count = sum(
            character.isalpha()
            for character in line
        )

        border_count = sum(
            character in "|+_=—–-"
            for character in line
        )

        border_ratio = (
            border_count / len(line)
            if line
            else 0.0
        )

        if (
            alphabetic_count < 3
            and border_ratio >= 0.40
        ):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def normalize_margin_text(value: str) -> str:
    """
    Normalise margin text so that changing page numbers still match.

    For example, "Annual Report 25" and "Annual Report 26" become the
    same normalized pattern.
    """

    value = remove_layout_artifacts(
        clean_raw_text(value)
    )

    value = value.lower()
    value = re.sub(r"\d+", "<number>", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def extract_page_blocks(
    page: pymupdf.Page,
    page_number: int,
) -> list[RawBlock]:
    """
    Extract text blocks with bounding-box and font metadata.
    """

    page_data = page.get_text(
        "dict",
        sort=False,
    )

    page_width = float(page.rect.width)
    page_height = float(page.rect.height)

    intermediate: list[dict] = []
    all_font_sizes: list[float] = []

    for block_index, block in enumerate(
        page_data.get("blocks", [])
    ):
        # PyMuPDF block type 0 represents text.
        if block.get("type") != 0:
            continue

        block_lines: list[str] = []
        font_sizes: list[float] = []
        fonts: list[str] = []

        for line in block.get("lines", []):
            line_parts: list[str] = []

            for span in line.get("spans", []):
                span_text = str(
                    span.get("text", "")
                )

                if span_text:
                    line_parts.append(span_text)

                size = float(
                    span.get("size", 0.0)
                )

                if size > 0:
                    font_sizes.append(size)
                    all_font_sizes.append(size)

                fonts.append(
                    str(
                        span.get("font", "")
                    ).lower()
                )

            line_text = "".join(
                line_parts
            ).strip()

            if line_text:
                block_lines.append(line_text)

        text = remove_layout_artifacts(
            clean_raw_text(
                "\n".join(block_lines)
            )
        )

        if not text:
            continue

        x0, y0, x1, y1 = (
            float(value)
            for value in block.get(
                "bbox",
                (0, 0, 0, 0),
            )
        )

        intermediate.append(
            {
                "text": text,
                "block_index": block_index,
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "font_sizes": font_sizes,
                "fonts": fonts,
            }
        )

    page_body_font = (
        float(median(all_font_sizes))
        if all_font_sizes
        else 0.0
    )

    blocks: list[RawBlock] = []

    for item in intermediate:
        font_sizes = item["font_sizes"]

        block_median_font = (
            float(median(font_sizes))
            if font_sizes
            else page_body_font
        )

        max_font_size = (
            max(font_sizes)
            if font_sizes
            else block_median_font
        )

        is_bold = any(
            term in font
            for font in item["fonts"]
            for term in BOLD_FONT_TERMS
        )

        blocks.append(
            RawBlock(
                text=item["text"],
                page_number=page_number,
                block_index=item["block_index"],
                x0=item["x0"],
                y0=item["y0"],
                x1=item["x1"],
                y1=item["y1"],
                page_width=page_width,
                page_height=page_height,
                max_font_size=max_font_size,
                median_font_size=block_median_font,
                is_bold=is_bold,
            )
        )

    return blocks


def detect_repeated_margin_blocks(
    pages: list[list[RawBlock]],
) -> set[str]:
    """
    Detect text blocks repeatedly appearing at the top or bottom of
    pages, such as report titles, company names and page numbers.
    """

    counts: Counter[str] = Counter()
    pages_with_candidates = 0

    for blocks in pages:
        page_candidates: set[str] = set()

        for block in blocks:
            top_limit = (
                block.page_height
                * TOP_MARGIN_RATIO
            )

            bottom_limit = (
                block.page_height
                * (1 - BOTTOM_MARGIN_RATIO)
            )

            if (
                block.y0 <= top_limit
                or block.y1 >= bottom_limit
            ):
                normalized = normalize_margin_text(
                    block.text
                )

                if normalized:
                    page_candidates.add(normalized)

        if page_candidates:
            pages_with_candidates += 1
            counts.update(page_candidates)

    required_count = max(
        MIN_REPEATED_MARGIN_PAGES,
        ceil(
            pages_with_candidates
            * REPEATED_MARGIN_RATIO
        ),
    )

    return {
        text
        for text, count in counts.items()
        if count >= required_count
    }


def read_pdf_blocks(
    pdf_path: str,
) -> list[list[RawBlock]]:
    """
    Extract every page in a PDF and remove repeated margin blocks.
    """

    with pymupdf.open(pdf_path) as document:
        pages = [
            extract_page_blocks(
                page,
                page_number=index + 1,
            )
            for index, page in enumerate(document)
        ]

    repeated_margins = detect_repeated_margin_blocks(
        pages
    )

    cleaned_pages: list[list[RawBlock]] = []

    for blocks in pages:
        retained = [
            block
            for block in blocks
            if normalize_margin_text(block.text)
            not in repeated_margins
        ]

        cleaned_pages.append(retained)

    return cleaned_pages
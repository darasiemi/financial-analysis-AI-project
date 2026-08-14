from __future__ import annotations

import logging
import re
from collections import Counter
from math import ceil
from statistics import median

import pymupdf

from ingestion.processing.config import (
    BOTTOM_MARGIN_RATIO,
    MIN_REPEATED_MARGIN_PAGES,
    REPEATED_MARGIN_RATIO,
    TABLE_BLOCK_OVERLAP_RATIO,
    TOP_MARGIN_RATIO,
)
from ingestion.processing.models import RawBlock

logger = logging.getLogger(__name__)


BOLD_FONT_TERMS = (
    "bold",
    "semibold",
    "demibold",
    "black",
    "heavy",
)


# ============================================================
# Text cleaning
# ============================================================


def clean_raw_text(
    value: str,
) -> str:
    """
    Perform conservative cleanup while preserving meaningful
    line boundaries.
    """

    value = value.replace(
        "\u00a0",
        " ",
    )

    value = value.replace(
        "\u00ad",
        "",
    )

    value = value.replace(
        "￾",
        "",
    )

    # Join words split across PDF line boundaries.
    value = re.sub(
        r"(?<=\w)-\s*\n\s*(?=\w)",
        "",
        value,
    )

    value = re.sub(
        r"[ \t]+",
        " ",
        value,
    )

    value = re.sub(
        r" *\n *",
        "\n",
        value,
    )

    value = re.sub(
        r"\n{3,}",
        "\n\n",
        value,
    )

    return value.strip()


def remove_layout_artifacts(
    text: str,
) -> str:
    """
    Remove border characters and layout fragments that may be
    represented as text objects inside a PDF.

    Examples:

        |
        +
        | + |
        ----------
        ==========
    """

    cleaned_lines: list[str] = []

    for raw_line in text.splitlines():

        line = raw_line.strip()

        if not line:
            continue

        # Lines containing only border/separator characters.
        if re.fullmatch(
            r"[\s|+_=—–\-│┃┆┊┋┇┌┐└┘├┤┬┴┼]+",
            line,
        ):
            continue

        # One or two isolated table-border symbols.
        if re.fullmatch(
            r"[|+│┃]{1,2}",
            line,
        ):
            continue

        # Combinations such as "| + |".
        if re.fullmatch(
            r"[|+│┃\s]+",
            line,
        ):
            continue

        alphabetic_count = sum(character.isalpha() for character in line)

        border_count = sum(character in "|+_=—–-│┃┆┊┋┇┌┐└┘├┤┬┴┼" for character in line)

        border_ratio = border_count / len(line) if line else 0.0

        if alphabetic_count < 3 and border_ratio >= 0.40:
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


# ============================================================
# Table detection for narrative exclusion
# ============================================================


def detect_table_bboxes(
    page: pymupdf.Page,
) -> list[
    tuple[
        float,
        float,
        float,
        float,
    ]
]:
    """
    Detect table regions on a page.

    Uses the same line-based strategy as the structured-table
    extraction pipeline.

    Only the bounding boxes are needed here; table contents are
    extracted separately by the report_tables pipeline.
    """

    try:

        finder = page.find_tables(
            strategy="lines",
        )

    except Exception as exc:

        logger.warning(
            "Table-region detection failed " "on page %d: %s",
            page.number + 1,
            exc,
        )

        return []

    bboxes: list[
        tuple[
            float,
            float,
            float,
            float,
        ]
    ] = []

    for table in finder.tables:

        try:

            bbox = table.bbox

            bboxes.append(
                (
                    float(bbox[0]),
                    float(bbox[1]),
                    float(bbox[2]),
                    float(bbox[3]),
                )
            )

        except Exception:
            continue

    return bboxes


def rectangle_area(
    bbox: tuple[
        float,
        float,
        float,
        float,
    ],
) -> float:
    """
    Return rectangular bounding-box area.
    """

    x0, y0, x1, y1 = bbox

    width = max(
        0.0,
        x1 - x0,
    )

    height = max(
        0.0,
        y1 - y0,
    )

    return width * height


def intersection_area(
    bbox_a: tuple[
        float,
        float,
        float,
        float,
    ],
    bbox_b: tuple[
        float,
        float,
        float,
        float,
    ],
) -> float:
    """
    Calculate the overlapping area of two rectangles.
    """

    ax0, ay0, ax1, ay1 = bbox_a
    bx0, by0, bx1, by1 = bbox_b

    overlap_width = max(
        0.0,
        min(ax1, bx1) - max(ax0, bx0),
    )

    overlap_height = max(
        0.0,
        min(ay1, by1) - max(ay0, by0),
    )

    return overlap_width * overlap_height


def block_table_overlap_ratio(
    block: RawBlock,
    table_bbox: tuple[
        float,
        float,
        float,
        float,
    ],
) -> float:
    """
    Calculate what proportion of a text block lies inside a
    detected table.

    Ratio is relative to the text-block area rather than the
    table area.
    """

    block_bbox = (
        block.x0,
        block.y0,
        block.x1,
        block.y1,
    )

    block_area = rectangle_area(block_bbox)

    if block_area <= 0:
        return 0.0

    overlap = intersection_area(
        block_bbox,
        table_bbox,
    )

    return overlap / block_area


def block_is_inside_table(
    block: RawBlock,
    table_bboxes: list[
        tuple[
            float,
            float,
            float,
            float,
        ]
    ],
) -> bool:
    """
    Return True when a substantial proportion of the block lies
    inside any detected table.

    This prevents structured financial rows from being duplicated
    in narrative chunks.
    """

    for table_bbox in table_bboxes:

        overlap_ratio = block_table_overlap_ratio(
            block,
            table_bbox,
        )

        if overlap_ratio >= TABLE_BLOCK_OVERLAP_RATIO:
            return True

    return False


def remove_table_blocks(
    blocks: list[RawBlock],
    table_bboxes: list[
        tuple[
            float,
            float,
            float,
            float,
        ]
    ],
) -> tuple[
    list[RawBlock],
    int,
]:
    """
    Remove text blocks substantially contained inside tables.

    Returns:
        retained blocks
        number of excluded blocks
    """

    if not table_bboxes:
        return blocks, 0

    retained: list[RawBlock] = []

    removed_count = 0

    for block in blocks:

        if block_is_inside_table(
            block,
            table_bboxes,
        ):

            removed_count += 1
            continue

        retained.append(block)

    return (
        retained,
        removed_count,
    )


# ============================================================
# Repeated margin detection
# ============================================================


def normalize_margin_text(
    value: str,
) -> str:
    """
    Normalize margin text so changing page numbers still match.

    Example:

        Annual Report 25
        Annual Report 26

    are normalized to the same pattern.
    """

    value = remove_layout_artifacts(clean_raw_text(value))

    value = value.lower()

    value = re.sub(
        r"\d+",
        "<number>",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# ============================================================
# Raw block extraction
# ============================================================


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

    for (
        block_index,
        block,
    ) in enumerate(
        page_data.get(
            "blocks",
            [],
        )
    ):

        # PyMuPDF block type 0 is text.
        if block.get("type") != 0:
            continue

        block_lines: list[str] = []

        font_sizes: list[float] = []

        fonts: list[str] = []

        for line in block.get(
            "lines",
            [],
        ):

            line_parts: list[str] = []

            for span in line.get(
                "spans",
                [],
            ):

                span_text = str(
                    span.get(
                        "text",
                        "",
                    )
                )

                if span_text:
                    line_parts.append(span_text)

                size = float(
                    span.get(
                        "size",
                        0.0,
                    )
                )

                if size > 0:

                    font_sizes.append(size)

                    all_font_sizes.append(size)

                fonts.append(
                    str(
                        span.get(
                            "font",
                            "",
                        )
                    ).lower()
                )

            line_text = "".join(line_parts).strip()

            if line_text:

                block_lines.append(line_text)

        text = remove_layout_artifacts(clean_raw_text("\n".join(block_lines)))

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
                "block_index": (block_index),
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "font_sizes": (font_sizes),
                "fonts": fonts,
            }
        )

    page_body_font = float(median(all_font_sizes)) if all_font_sizes else 0.0

    blocks: list[RawBlock] = []

    for item in intermediate:

        font_sizes = item["font_sizes"]

        block_median_font = float(median(font_sizes)) if font_sizes else page_body_font

        max_font_size = max(font_sizes) if font_sizes else block_median_font

        is_bold = any(
            term in font for font in item["fonts"] for term in BOLD_FONT_TERMS
        )

        blocks.append(
            RawBlock(
                text=item["text"],
                page_number=(page_number),
                block_index=item["block_index"],
                x0=item["x0"],
                y0=item["y0"],
                x1=item["x1"],
                y1=item["y1"],
                page_width=(page_width),
                page_height=(page_height),
                max_font_size=(max_font_size),
                median_font_size=(block_median_font),
                is_bold=is_bold,
            )
        )

    return blocks


# ============================================================
# Header/footer removal
# ============================================================


def detect_repeated_margin_blocks(
    pages: list[list[RawBlock]],
) -> set[str]:
    """
    Detect text repeatedly appearing at page margins.
    """

    counts: Counter[str] = Counter()

    pages_with_candidates = 0

    for blocks in pages:

        page_candidates: set[str] = set()

        for block in blocks:

            top_limit = block.page_height * TOP_MARGIN_RATIO

            bottom_limit = block.page_height * (1 - BOTTOM_MARGIN_RATIO)

            if block.y0 <= top_limit or block.y1 >= bottom_limit:

                normalized = normalize_margin_text(block.text)

                if normalized:

                    page_candidates.add(normalized)

        if page_candidates:

            pages_with_candidates += 1

            counts.update(page_candidates)

    required_count = max(
        MIN_REPEATED_MARGIN_PAGES,
        ceil(pages_with_candidates * REPEATED_MARGIN_RATIO),
    )

    return {text for text, count in counts.items() if count >= required_count}


# ============================================================
# Main PDF reader
# ============================================================


def read_pdf_blocks(
    pdf_path: str,
) -> list[list[RawBlock]]:
    """
    Extract narrative text blocks from a PDF.

    Processing order:

        PDF
          ↓
        text blocks
          ↓
        detect table bounding boxes
          ↓
        remove blocks substantially inside tables
          ↓
        detect/remove repeated headers and footers
          ↓
        narrative-only page blocks

    Structured table content is intentionally handled by the
    separate report_tables pipeline.
    """

    pages: list[list[RawBlock]] = []

    total_table_blocks_removed = 0

    pages_with_tables = 0

    with pymupdf.open(pdf_path) as document:

        for page_index, page in enumerate(document):

            page_number = page_index + 1

            blocks = extract_page_blocks(
                page,
                page_number,
            )

            table_bboxes = detect_table_bboxes(page)

            if table_bboxes:

                pages_with_tables += 1

            (
                blocks,
                removed_count,
            ) = remove_table_blocks(
                blocks,
                table_bboxes,
            )

            total_table_blocks_removed += removed_count

            pages.append(blocks)

    # Detect repeated margins only after table blocks have been
    # removed. Table rows should not influence header/footer
    # frequency detection.
    repeated_margins = detect_repeated_margin_blocks(pages)

    cleaned_pages: list[list[RawBlock]] = []

    for blocks in pages:

        retained = [
            block
            for block in blocks
            if (normalize_margin_text(block.text) not in repeated_margins)
        ]

        cleaned_pages.append(retained)

    logger.info(
        (
            "Narrative extraction: "
            "%d page(s) contained detected tables; "
            "%d text block(s) excluded from narrative."
        ),
        pages_with_tables,
        total_table_blocks_removed,
    )

    return cleaned_pages

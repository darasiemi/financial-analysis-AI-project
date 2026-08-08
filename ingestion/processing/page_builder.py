from __future__ import annotations

import re
from statistics import median

from ingestion.processing.config import (
    CALLOUT_FONT_RATIO,
    CALLOUT_MAX_WORDS,
    COLUMN_GAP_RATIO,
    FULL_WIDTH_RATIO,
    MAX_PARAGRAPH_WORDS,
    MIN_BLOCK_WORDS,
    MIN_COLUMN_WORDS,
    PARAGRAPH_GAP_RATIO,
)
from ingestion.processing.models import (
    ProcessedPage,
    RawBlock,
)


COMMON_SECTION_TERMS = (
    "business overview",
    "strategic report",
    "our strategy",
    "risk management",
    "corporate governance",
    "directors' report",
    "directors’ report",
    "financial statements",
    "financial review",
    "notes to the",
    "independent auditor",
    "sustainability",
    "shareholder information",
    "investor information",
    "operating review",
    "business performance",
    "chairman’s statement",
    "chairman's statement",
    "chief executive",
    "audit opinion",
    "accounting policies",
    "statement of financial position",
    "statement of cash flows",
)


LAYOUT_TOKEN_PATTERN = re.compile(
    r"^[|+_=—–│┃┆┊┋┇┌┐└┘├┤┬┴┼]+$"
)


# ============================================================
# Basic text normalization
# ============================================================


def normalize_text(
    value: str,
) -> str:
    value = value.replace("\u00a0", " ")
    value = value.replace("\u00ad", "")
    value = value.replace("￾", "")

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


def strip_layout_tokens(
    text: str,
) -> str:
    """
    Remove isolated PDF layout symbols that survived block-level
    cleaning.

    This operates after reconstruction, which is important because
    some artifacts only become visible after blocks are concatenated.
    """

    tokens = text.split()

    retained: list[str] = []

    for token in tokens:
        stripped = token.strip()

        if not stripped:
            continue

        if LAYOUT_TOKEN_PATTERN.fullmatch(
            stripped
        ):
            continue

        retained.append(token)

    text = " ".join(retained)

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def flatten_block_text(
    value: str,
) -> str:
    value = normalize_text(value)

    value = re.sub(
        r"\s*\n\s*",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return strip_layout_tokens(
        value
    )


# ============================================================
# Noise detection
# ============================================================


def alphabetic_density(
    text: str,
) -> float:
    useful_characters = [
        character
        for character in text
        if not character.isspace()
    ]

    if not useful_characters:
        return 0.0

    letters = sum(
        character.isalpha()
        for character in useful_characters
    )

    return (
        letters
        / len(useful_characters)
    )


def is_noise_paragraph(
    text: str,
) -> bool:
    cleaned = strip_layout_tokens(
        text.strip()
    )

    if not cleaned:
        return True

    words = cleaned.split()

    alphabetic_count = sum(
        character.isalpha()
        for character in cleaned
    )

    symbol_count = sum(
        character
        in "|+_=—–│┃┆┊┋┇┌┐└┘├┤┬┴┼"
        for character in cleaned
    )

    symbol_ratio = (
        symbol_count / len(cleaned)
        if cleaned
        else 0.0
    )

    if symbol_ratio >= 0.25:
        return True

    if re.fullmatch(
        r"[\s|+\-_=—–.│┃┆┊┋┇┌┐└┘├┤┬┴┼]{3,}",
        cleaned,
    ):
        return True

    if (
        len(words) <= 2
        and alphabetic_count == 0
    ):
        return True

    if alphabetic_count < 5:
        return True

    # Only use density as a rejection criterion for short fragments.
    # Genuine financial tables can naturally have low letter density.
    if (
        len(words) <= 12
        and alphabetic_density(cleaned) < 0.25
    ):
        return True

    return False


def clean_reconstructed_paragraph(
    text: str,
) -> str:
    """
    Second cleaning pass after blocks have been merged.
    """

    text = normalize_text(text)
    text = strip_layout_tokens(text)

    # Remove repeated isolated visual separators.
    text = re.sub(
        r"(?:\s+[|+│┃┆┊┋┇]){2,}",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def is_decorative_block(
    block: RawBlock,
) -> bool:
    text = flatten_block_text(
        block.text
    )

    words = text.split()

    if is_noise_paragraph(text):
        return True

    if len(words) >= MIN_BLOCK_WORDS:
        return False

    if re.fullmatch(
        r"[\d\s.,%₦N$€£+|/–—-]+",
        text,
    ):
        return True

    return len(text) <= 2


# ============================================================
# Heading detection
# ============================================================


def is_likely_heading(
    block: RawBlock,
    body_font_size: float,
) -> bool:
    text = flatten_block_text(
        block.text
    )

    words = text.split()

    if not 1 <= len(words) <= 16:
        return False

    if len(text) > 160:
        return False

    if text.endswith(
        (".", ",", ";")
    ):
        return False

    if re.fullmatch(
        r"[\d\s./%₦N$€£|–—-]+",
        text,
    ):
        return False

    lowered = text.lower()

    known_heading = any(
        term in lowered
        for term in COMMON_SECTION_TERMS
    )

    large_font = (
        body_font_size > 0
        and block.max_font_size
        >= body_font_size * 1.25
    )

    return (
        known_heading
        or (
            block.is_bold
            and large_font
        )
    )


def is_probable_callout(
    block: RawBlock,
    body_font_size: float,
) -> bool:
    """
    Detect large, short slogans/pull-quotes that are visually
    prominent but often disruptive for document reading order.

    Example:
        "To be Africa's..."
    """

    text = flatten_block_text(
        block.text
    )

    words = text.split()

    if not words:
        return False

    if len(words) > CALLOUT_MAX_WORDS:
        return False

    # Legitimate headings must remain.
    if is_likely_heading(
        block,
        body_font_size,
    ):
        return False

    substantially_larger = (
        body_font_size > 0
        and block.max_font_size
        >= body_font_size
        * CALLOUT_FONT_RATIO
    )

    return substantially_larger


# ============================================================
# Improved reading order
# ============================================================


def block_width(
    block: RawBlock,
) -> float:
    return max(
        0.0,
        block.x1 - block.x0,
    )


def block_center_y(
    block: RawBlock,
) -> float:
    return (
        block.y0 + block.y1
    ) / 2


def block_center_x(
    block: RawBlock,
) -> float:
    return (
        block.x0 + block.x1
    ) / 2


def is_full_width_block(
    block: RawBlock,
) -> bool:
    if block.page_width <= 0:
        return False

    return (
        block_width(block)
        / block.page_width
        >= FULL_WIDTH_RATIO
    )


def region_is_two_column(
    blocks: list[RawBlock],
) -> bool:
    """
    Detect whether a vertical page region genuinely contains two
    substantial columns.
    """

    if not blocks:
        return False

    page_width = blocks[0].page_width
    midpoint = page_width / 2

    tolerance = (
        page_width
        * COLUMN_GAP_RATIO
    )

    left = [
        block
        for block in blocks
        if block_center_x(block)
        < midpoint - tolerance / 2
    ]

    right = [
        block
        for block in blocks
        if block_center_x(block)
        >= midpoint + tolerance / 2
    ]

    left_words = sum(
        len(
            flatten_block_text(
                block.text
            ).split()
        )
        for block in left
    )

    right_words = sum(
        len(
            flatten_block_text(
                block.text
            ).split()
        )
        for block in right
    )

    return (
        left_words >= MIN_COLUMN_WORDS
        and right_words >= MIN_COLUMN_WORDS
    )


def order_region_blocks(
    blocks: list[RawBlock],
) -> list[RawBlock]:
    """
    Order one vertical region independently.

    This avoids assuming that the entire PDF page uses one layout.
    """

    if not blocks:
        return []

    if not region_is_two_column(
        blocks
    ):
        return sorted(
            blocks,
            key=lambda block: (
                block.y0,
                block.x0,
                block.block_index,
            ),
        )

    page_width = blocks[0].page_width
    midpoint = page_width / 2

    left: list[RawBlock] = []
    right: list[RawBlock] = []
    centre: list[RawBlock] = []

    for block in blocks:
        centre_x = block_center_x(
            block
        )

        if centre_x < midpoint:
            left.append(block)
        elif centre_x > midpoint:
            right.append(block)
        else:
            centre.append(block)

    left.sort(
        key=lambda block: (
            block.y0,
            block.x0,
        )
    )

    right.sort(
        key=lambda block: (
            block.y0,
            block.x0,
        )
    )

    centre.sort(
        key=lambda block: (
            block.y0,
            block.x0,
        )
    )

    return (
        left
        + centre
        + right
    )


def order_page_blocks(
    blocks: list[RawBlock],
) -> list[RawBlock]:
    """
    Reconstruct reading order using full-width blocks as vertical
    layout anchors.

    Instead of assuming the whole page is:

        left column -> right column

    the page is broken into independent vertical regions:

        region
        full-width anchor
        region
        full-width anchor
        region

    Each region gets its own one-column/two-column decision.
    """

    preliminary = [
        block
        for block in blocks
        if not is_decorative_block(
            block
        )
    ]

    if not preliminary:
        return []

    font_sizes = [
        block.median_font_size
        for block in preliminary
        if block.median_font_size > 0
    ]

    body_font_size = (
        float(
            median(font_sizes)
        )
        if font_sizes
        else 0.0
    )

    usable = [
        block
        for block in preliminary
        if not is_probable_callout(
            block,
            body_font_size,
        )
    ]

    if not usable:
        return []

    anchors = [
        block
        for block in usable
        if is_full_width_block(
            block
        )
    ]

    non_anchors = [
        block
        for block in usable
        if not is_full_width_block(
            block
        )
    ]

    # No anchors: simply order the page as one region.
    if not anchors:
        return order_region_blocks(
            non_anchors
        )

    anchors.sort(
        key=lambda block: (
            block.y0,
            block.x0,
        )
    )

    output: list[RawBlock] = []

    remaining = list(
        non_anchors
    )

    previous_boundary = float(
        "-inf"
    )

    for anchor in anchors:
        anchor_y = block_center_y(
            anchor
        )

        region = [
            block
            for block in remaining
            if (
                previous_boundary
                < block_center_y(block)
                < anchor_y
            )
        ]

        output.extend(
            order_region_blocks(
                region
            )
        )

        output.append(anchor)

        region_ids = {
            id(block)
            for block in region
        }

        remaining = [
            block
            for block in remaining
            if id(block)
            not in region_ids
        ]

        previous_boundary = (
            anchor_y
        )

    # Everything below the final anchor.
    output.extend(
        order_region_blocks(
            remaining
        )
    )

    return output


# ============================================================
# Contents/table helpers
# ============================================================


def is_contents_page(
    blocks: list[RawBlock],
) -> bool:
    text = "\n".join(
        block.text
        for block in blocks
    )

    lowered = text.lower()

    has_marker = any(
        marker in lowered
        for marker in (
            "contents",
            "in this report",
            "\nindex",
        )
    )

    isolated_numbers = sum(
        bool(
            re.fullmatch(
                r"\s*\d{1,3}\s*",
                line,
            )
        )
        for line in text.splitlines()
    )

    return (
        has_marker
        and isolated_numbers >= 5
    )


def is_table_like_page(
    ordered_blocks: list[RawBlock],
) -> bool:
    lines: list[str] = []

    for block in ordered_blocks:
        lines.extend(
            line.strip()
            for line in block.text.splitlines()
            if line.strip()
        )

    if len(lines) < 10:
        return False

    number_pattern = re.compile(
        r"\(?[-–—]?"
        r"(?:₦|N|\$|£|€)?"
        r"\d[\d,]*"
        r"(?:\.\d+)?%?\)?"
    )

    multiple_number_rows = sum(
        len(
            number_pattern.findall(
                line
            )
        )
        >= 2
        for line in lines
    )

    numeric_end_rows = sum(
        bool(
            re.search(
                r"(?:"
                r"\(?[-–—]?"
                r"(?:₦|N|\$|£|€)?"
                r"\d[\d,]*"
                r"(?:\.\d+)?%?\)?"
                r"|[-–—]"
                r")\s*$",
                line,
            )
        )
        for line in lines
    )

    return (
        multiple_number_rows
        / len(lines)
        >= 0.45
        and numeric_end_rows
        / len(lines)
        >= 0.50
    )


# ============================================================
# Paragraph reconstruction
# ============================================================


def blocks_are_in_same_column(
    previous: RawBlock,
    current: RawBlock,
) -> bool:
    overlap = max(
        0.0,
        min(
            previous.x1,
            current.x1,
        )
        - max(
            previous.x0,
            current.x0,
        ),
    )

    narrower_width = min(
        previous.x1
        - previous.x0,
        current.x1
        - current.x0,
    )

    if narrower_width <= 0:
        return False

    return (
        overlap
        / narrower_width
        >= 0.45
    )


def starts_like_new_paragraph(
    text: str,
) -> bool:
    return bool(
        re.match(
            r"^(?:"
            r"\d+(?:\.\d+)*[.)]?"
            r"|[A-Z][.)]"
            r"|[-•▪‣]"
            r")\s+",
            text,
        )
    )


def should_start_new_paragraph(
    previous: RawBlock,
    current: RawBlock,
) -> bool:
    current_text = (
        flatten_block_text(
            current.text
        )
    )

    previous_text = (
        flatten_block_text(
            previous.text
        )
    )

    if not blocks_are_in_same_column(
        previous,
        current,
    ):
        return True

    vertical_gap = (
        current.y0
        - previous.y1
    )

    gap_threshold = (
        current.page_height
        * PARAGRAPH_GAP_RATIO
    )

    if vertical_gap > gap_threshold:
        return True

    if starts_like_new_paragraph(
        current_text
    ):
        return True

    if previous_text.endswith(
        (".", "?", "!", ":")
    ):
        return True

    return False


def split_oversized_paragraph(
    paragraph: str,
) -> list[str]:
    words = paragraph.split()

    if (
        len(words)
        <= MAX_PARAGRAPH_WORDS
    ):
        return [paragraph]

    sentences = [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+",
            paragraph,
        )
        if sentence.strip()
    ]

    if len(sentences) <= 1:
        return [
            " ".join(
                words[
                    index:
                    index
                    + MAX_PARAGRAPH_WORDS
                ]
            )
            for index in range(
                0,
                len(words),
                MAX_PARAGRAPH_WORDS,
            )
        ]

    output: list[str] = []

    current: list[str] = []
    current_word_count = 0

    for sentence in sentences:
        sentence_word_count = len(
            sentence.split()
        )

        if (
            current
            and current_word_count
            + sentence_word_count
            > MAX_PARAGRAPH_WORDS
        ):
            output.append(
                " ".join(
                    current
                )
            )

            current = []
            current_word_count = 0

        current.append(
            sentence
        )

        current_word_count += (
            sentence_word_count
        )

    if current:
        output.append(
            " ".join(current)
        )

    return output


def reconstruct_paragraphs(
    ordered_blocks: list[RawBlock],
    body_font_size: float,
    current_section: str | None,
) -> tuple[
    list[str],
    str | None,
]:
    paragraphs: list[str] = []

    current_parts: list[str] = []

    previous_content_block: (
        RawBlock | None
    ) = None

    def flush_current() -> None:
        nonlocal current_parts

        if not current_parts:
            return

        paragraph = (
            clean_reconstructed_paragraph(
                " ".join(
                    current_parts
                )
            )
        )

        if (
            paragraph
            and not is_noise_paragraph(
                paragraph
            )
        ):
            paragraphs.extend(
                split_oversized_paragraph(
                    paragraph
                )
            )

        current_parts = []

    for block in ordered_blocks:
        text = flatten_block_text(
            block.text
        )

        if (
            not text
            or is_noise_paragraph(
                text
            )
        ):
            continue

        if is_likely_heading(
            block,
            body_font_size,
        ):
            flush_current()

            current_section = text

            previous_content_block = None

            continue

        if (
            previous_content_block
            is not None
            and should_start_new_paragraph(
                previous_content_block,
                block,
            )
        ):
            flush_current()

        current_parts.append(
            text
        )

        previous_content_block = (
            block
        )

    flush_current()

    # Final second-pass cleanup.
    final_paragraphs: list[str] = []

    for paragraph in paragraphs:
        cleaned = (
            clean_reconstructed_paragraph(
                paragraph
            )
        )

        if (
            cleaned
            and len(
                cleaned.split()
            )
            >= 2
            and not is_noise_paragraph(
                cleaned
            )
        ):
            final_paragraphs.append(
                cleaned
            )

    return (
        final_paragraphs,
        current_section,
    )


# ============================================================
# Page reconstruction
# ============================================================


def build_page(
    blocks: list[RawBlock],
    current_section: str | None,
) -> tuple[
    ProcessedPage | None,
    str | None,
]:
    if not blocks:
        return (
            None,
            current_section,
        )

    if is_contents_page(
        blocks
    ):
        return (
            None,
            current_section,
        )

    ordered = order_page_blocks(
        blocks
    )

    if not ordered:
        return (
            None,
            current_section,
        )

    font_sizes = [
        block.median_font_size
        for block in ordered
        if block.median_font_size > 0
    ]

    body_font_size = (
        float(
            median(
                font_sizes
            )
        )
        if font_sizes
        else 0.0
    )

    (
        paragraphs,
        current_section,
    ) = reconstruct_paragraphs(
        ordered_blocks=ordered,
        body_font_size=body_font_size,
        current_section=current_section,
    )

    total_words = sum(
        len(
            paragraph.split()
        )
        for paragraph in paragraphs
    )

    if total_words < 10:
        return (
            None,
            current_section,
        )

    return (
        ProcessedPage(
            page_number=(
                ordered[0]
                .page_number
            ),
            paragraphs=tuple(
                paragraphs
            ),
            section_title=(
                current_section
            ),
            contains_table=(
                is_table_like_page(
                    ordered
                )
            ),
        ),
        current_section,
    )


def reconstruct_document_pages(
    pages: list[list[RawBlock]],
) -> list[ProcessedPage]:
    processed_pages: list[
        ProcessedPage
    ] = []

    current_section: (
        str | None
    ) = None

    for blocks in pages:
        (
            page,
            current_section,
        ) = build_page(
            blocks,
            current_section,
        )

        if page is not None:
            processed_pages.append(
                page
            )

    return processed_pages
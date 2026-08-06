from __future__ import annotations

import re
from statistics import median

from ingestion.processing.config import (
    COLUMN_GAP_RATIO,
    MAX_PARAGRAPH_WORDS,
    MIN_BLOCK_WORDS,
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


def normalize_text(value: str) -> str:
    """
    Conservatively normalize extracted PDF text.
    """

    value = value.replace("\u00a0", " ")
    value = value.replace("\u00ad", "")
    value = value.replace("￾", "")

    # Join words broken across extracted line boundaries.
    value = re.sub(
        r"(?<=\w)-\s*\n\s*(?=\w)",
        "",
        value,
    )

    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)

    return value.strip()


def flatten_block_text(value: str) -> str:
    """
    Flatten visual line wrapping inside one layout block.
    """

    value = normalize_text(value)
    value = re.sub(r"\s*\n\s*", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def is_noise_paragraph(text: str) -> bool:
    """
    Identify low-information layout fragments.

    This removes extracted table-border characters while retaining
    useful bullet points and narrative text.
    """

    cleaned = text.strip()

    if not cleaned:
        return True

    words = cleaned.split()

    symbol_count = sum(
        character in "|+-_=—–"
        for character in cleaned
    )

    symbol_ratio = (
        symbol_count / len(cleaned)
        if cleaned
        else 0.0
    )

    alphabetic_count = sum(
        character.isalpha()
        for character in cleaned
    )

    # Paragraph dominated by border/separator symbols.
    if symbol_ratio >= 0.25:
        return True

    # Pure horizontal separator or border line.
    if re.fullmatch(
        r"[\s|+\-_=—–.]{3,}",
        cleaned,
    ):
        return True

    # Isolated numerical or symbol-only fragments.
    if (
        len(words) <= 2
        and alphabetic_count == 0
    ):
        return True

    # Every word consists only of borders, numbers or punctuation.
    if words and all(
        re.fullmatch(
            r"[|+\-_=—–.\d]+",
            word,
        )
        for word in words
    ):
        return True

    # Almost no alphabetic information.
    if alphabetic_count < 5:
        return True

    return False


def is_decorative_block(block: RawBlock) -> bool:
    """
    Filter isolated page numbers, decorative metrics and artifacts.
    """

    text = flatten_block_text(block.text)
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


def detect_column_count(
    blocks: list[RawBlock],
) -> int:
    """
    Conservatively detect whether a page contains one or two columns.
    """

    if not blocks:
        return 1

    page_width = blocks[0].page_width
    midpoint = page_width / 2
    tolerance = page_width * COLUMN_GAP_RATIO

    left_blocks = [
        block
        for block in blocks
        if block.x1 <= midpoint + tolerance
    ]

    right_blocks = [
        block
        for block in blocks
        if block.x0 >= midpoint - tolerance
    ]

    left_words = sum(
        len(
            flatten_block_text(
                block.text
            ).split()
        )
        for block in left_blocks
    )

    right_words = sum(
        len(
            flatten_block_text(
                block.text
            ).split()
        )
        for block in right_blocks
    )

    if left_words >= 40 and right_words >= 40:
        return 2

    return 1


def order_page_blocks(
    blocks: list[RawBlock],
) -> list[RawBlock]:
    """
    Order blocks according to an approximate human reading sequence.

    One-column pages are ordered top-to-bottom. Two-column pages are
    ordered using full-width headings first, followed by the left
    column and then the right column.
    """

    usable_blocks = [
        block
        for block in blocks
        if not is_decorative_block(block)
    ]

    if not usable_blocks:
        return []

    if detect_column_count(usable_blocks) == 1:
        return sorted(
            usable_blocks,
            key=lambda block: (
                round(block.y0, 1),
                round(block.x0, 1),
                block.block_index,
            ),
        )

    page_width = usable_blocks[0].page_width
    midpoint = page_width / 2

    full_width: list[RawBlock] = []
    left_column: list[RawBlock] = []
    right_column: list[RawBlock] = []

    for block in usable_blocks:
        block_width = block.x1 - block.x0
        block_centre = (
            block.x0 + block.x1
        ) / 2

        if block_width >= page_width * 0.70:
            full_width.append(block)
        elif block_centre < midpoint:
            left_column.append(block)
        else:
            right_column.append(block)

    full_width.sort(
        key=lambda block: (
            block.y0,
            block.x0,
        )
    )

    left_column.sort(
        key=lambda block: (
            block.y0,
            block.x0,
        )
    )

    right_column.sort(
        key=lambda block: (
            block.y0,
            block.x0,
        )
    )

    first_column_y = min(
        [
            block.y0
            for block in (
                left_column
                + right_column
            )
        ]
        or [float("inf")]
    )

    top_full_width = [
        block
        for block in full_width
        if block.y0 <= first_column_y
    ]

    lower_full_width = [
        block
        for block in full_width
        if block not in top_full_width
    ]

    return (
        top_full_width
        + left_column
        + right_column
        + lower_full_width
    )


def is_likely_heading(
    block: RawBlock,
    body_font_size: float,
) -> bool:
    """
    Detect probable section headings using wording and typography.
    """

    text = flatten_block_text(block.text)
    words = text.split()

    if not 1 <= len(words) <= 16:
        return False

    if len(text) > 160:
        return False

    if text.endswith((".", ",", ";")):
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


def is_contents_page(
    blocks: list[RawBlock],
) -> bool:
    """
    Identify contents and index pages that would create noisy
    retrieval matches.
    """

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
    """
    Apply a conservative table-content flag to a reconstructed page.

    This flag is metadata only and does not alter the chunking flow.
    """

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
        r"\(?[-–—]?(?:₦|N|\$|£|€)?"
        r"\d[\d,]*(?:\.\d+)?%?\)?"
    )

    multiple_number_rows = sum(
        len(number_pattern.findall(line)) >= 2
        for line in lines
    )

    numeric_end_rows = sum(
        bool(
            re.search(
                r"(?:"
                r"\(?[-–—]?(?:₦|N|\$|£|€)?"
                r"\d[\d,]*(?:\.\d+)?%?\)?"
                r"|[-–—]"
                r")\s*$",
                line,
            )
        )
        for line in lines
    )

    return (
        multiple_number_rows / len(lines) >= 0.45
        and numeric_end_rows / len(lines) >= 0.50
    )


def blocks_are_in_same_column(
    previous: RawBlock,
    current: RawBlock,
) -> bool:
    """
    Check whether two blocks substantially overlap horizontally.
    """

    overlap = max(
        0.0,
        min(previous.x1, current.x1)
        - max(previous.x0, current.x0),
    )

    narrower_width = min(
        previous.x1 - previous.x0,
        current.x1 - current.x0,
    )

    if narrower_width <= 0:
        return False

    return (
        overlap / narrower_width >= 0.45
    )


def starts_like_new_paragraph(text: str) -> bool:
    """
    Detect numbered, lettered and bulleted paragraph starts.
    """

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
    """
    Determine whether the current block begins a new paragraph.
    """

    current_text = flatten_block_text(
        current.text
    )

    previous_text = flatten_block_text(
        previous.text
    )

    if not blocks_are_in_same_column(
        previous,
        current,
    ):
        return True

    vertical_gap = (
        current.y0 - previous.y1
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
    """
    Split unusually long reconstructed paragraphs at sentence
    boundaries where possible.
    """

    words = paragraph.split()

    if len(words) <= MAX_PARAGRAPH_WORDS:
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
                    index + MAX_PARAGRAPH_WORDS
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
                " ".join(current)
            )

            current = []
            current_word_count = 0

        current.append(sentence)
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
) -> tuple[list[str], str | None]:
    """
    Convert ordered layout blocks into coherent paragraph units.

    Headings update section metadata but are not added as standalone
    paragraphs because the section title is already stored separately.
    """

    paragraphs: list[str] = []
    current_parts: list[str] = []
    previous_content_block: RawBlock | None = None

    def flush_current() -> None:
        nonlocal current_parts

        if not current_parts:
            return

        paragraph = normalize_text(
            " ".join(current_parts)
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
            or is_noise_paragraph(text)
        ):
            continue

        if is_likely_heading(
            block,
            body_font_size,
        ):
            flush_current()

            # Store headings as metadata rather than duplicate text.
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

        current_parts.append(text)
        previous_content_block = block

    flush_current()

    return paragraphs, current_section


def build_page(
    blocks: list[RawBlock],
    current_section: str | None,
) -> tuple[
    ProcessedPage | None,
    str | None,
]:
    """
    Reconstruct one PDF page into paragraph-level content.
    """

    if not blocks:
        return None, current_section

    if is_contents_page(blocks):
        return None, current_section

    ordered = order_page_blocks(blocks)

    if not ordered:
        return None, current_section

    font_sizes = [
        block.median_font_size
        for block in ordered
        if block.median_font_size > 0
    ]

    body_font_size = (
        float(median(font_sizes))
        if font_sizes
        else 0.0
    )

    paragraphs, current_section = (
        reconstruct_paragraphs(
            ordered_blocks=ordered,
            body_font_size=body_font_size,
            current_section=current_section,
        )
    )

    paragraphs = [
        paragraph
        for paragraph in paragraphs
        if len(paragraph.split()) >= 2
        and not is_noise_paragraph(paragraph)
    ]

    total_words = sum(
        len(paragraph.split())
        for paragraph in paragraphs
    )

    if total_words < 10:
        return None, current_section

    return (
        ProcessedPage(
            page_number=ordered[0].page_number,
            paragraphs=tuple(paragraphs),
            section_title=current_section,
            contains_table=is_table_like_page(
                ordered
            ),
        ),
        current_section,
    )


def reconstruct_document_pages(
    pages: list[list[RawBlock]],
) -> list[ProcessedPage]:
    """
    Reconstruct every usable page in a PDF.
    """

    processed_pages: list[ProcessedPage] = []
    current_section: str | None = None

    for blocks in pages:
        page, current_section = build_page(
            blocks,
            current_section,
        )

        if page is not None:
            processed_pages.append(page)

    return processed_pages
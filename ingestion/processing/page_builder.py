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


# ============================================================
# Known section-heading terminology
# ============================================================


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


# ============================================================
# Text normalization
# ============================================================


def normalize_text(
    value: str,
) -> str:
    """
    Conservatively normalize extracted PDF text.

    This removes PDF-specific spacing artifacts while preserving
    the actual wording of the document.
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

    # Rejoin words broken across PDF line boundaries.
    #
    # Example:
    #     finan-
    #     cial
    #
    # becomes:
    #     financial
    value = re.sub(
        r"(?<=\w)-\s*\n\s*(?=\w)",
        "",
        value,
    )

    # Normalize horizontal whitespace.
    value = re.sub(
        r"[ \t]+",
        " ",
        value,
    )

    # Remove whitespace surrounding line breaks.
    value = re.sub(
        r" *\n *",
        "\n",
        value,
    )

    # Do not preserve large visual gaps from the PDF.
    value = re.sub(
        r"\n{3,}",
        "\n\n",
        value,
    )

    return value.strip()


def flatten_block_text(
    value: str,
) -> str:
    """
    Convert visual line wrapping inside one PDF text block into
    normal prose.

    Example:

        The Group delivered
        strong financial
        performance.

    becomes:

        The Group delivered strong financial performance.
    """

    value = normalize_text(
        value
    )

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

    return value.strip()


# ============================================================
# Noise / artifact filtering
# ============================================================


def is_noise_paragraph(
    text: str,
) -> bool:
    """
    Identify low-information PDF layout fragments.

    Actual table regions should already have been removed by
    pdf_reader.py. This function therefore acts as an additional
    safeguard against residual PDF artifacts.
    """

    cleaned = text.strip()

    if not cleaned:
        return True

    words = cleaned.split()

    border_characters = (
        "|+-_=—–"
        "│┃┆┊┋┇"
        "┌┐└┘├┤┬┴┼"
    )

    symbol_count = sum(
        character in border_characters
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

    # --------------------------------------------------------
    # Border-dominated fragments
    # --------------------------------------------------------

    if symbol_ratio >= 0.25:
        return True

    # --------------------------------------------------------
    # Pure horizontal / layout separators
    # --------------------------------------------------------

    if re.fullmatch(
        r"[\s|+\-_=—–.│┃┆┊┋┇┌┐└┘├┤┬┴┼]{3,}",
        cleaned,
    ):
        return True

    # --------------------------------------------------------
    # Isolated numerical or symbol-only fragments
    # --------------------------------------------------------

    if (
        len(words) <= 2
        and alphabetic_count == 0
    ):
        return True

    # --------------------------------------------------------
    # Everything consists of numbers / separators
    # --------------------------------------------------------

    if words and all(
        re.fullmatch(
            r"[|+\-_=—–.│┃┆┊┋┇\d]+",
            word,
        )
        for word in words
    ):
        return True

    # --------------------------------------------------------
    # Almost no meaningful alphabetic information
    # --------------------------------------------------------

    if alphabetic_count < 5:
        return True

    return False


def is_decorative_block(
    block: RawBlock,
) -> bool:
    """
    Filter isolated page numbers, decorative metrics,
    and residual PDF layout fragments.
    """

    text = flatten_block_text(
        block.text
    )

    words = text.split()

    if is_noise_paragraph(
        text
    ):
        return True

    # Normal text containing enough words should remain.
    if len(words) >= MIN_BLOCK_WORDS:
        return False

    # Short numerical / currency fragments are usually layout noise.
    if re.fullmatch(
        r"[\d\s.,%₦N$€£+|/–—-]+",
        text,
    ):
        return True

    return len(text) <= 2


# ============================================================
# Column detection
# ============================================================


def detect_column_count(
    blocks: list[RawBlock],
) -> int:
    """
    Conservatively determine whether a page contains one or
    two narrative columns.

    Table blocks have already been removed upstream, so this
    primarily deals with narrative layouts.
    """

    if not blocks:
        return 1

    page_width = (
        blocks[0].page_width
    )

    midpoint = (
        page_width / 2
    )

    tolerance = (
        page_width
        * COLUMN_GAP_RATIO
    )

    left_blocks = [
        block
        for block in blocks
        if block.x1
        <= midpoint + tolerance
    ]

    right_blocks = [
        block
        for block in blocks
        if block.x0
        >= midpoint - tolerance
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

    # Both sides need substantial narrative content before the
    # page is treated as genuinely two-column.
    if (
        left_words >= 40
        and right_words >= 40
    ):
        return 2

    return 1


# ============================================================
# Reading-order reconstruction
# ============================================================


def order_page_blocks(
    blocks: list[RawBlock],
) -> list[RawBlock]:
    """
    Order narrative blocks according to an approximate human
    reading sequence.

    One-column page:
        top -> bottom

    Two-column page:
        full-width material at the top
        -> left column
        -> right column
        -> remaining full-width material

    Structured table blocks should already have been removed
    by pdf_reader.py.
    """

    usable_blocks = [
        block
        for block in blocks
        if not is_decorative_block(
            block
        )
    ]

    if not usable_blocks:
        return []

    # --------------------------------------------------------
    # One-column page
    # --------------------------------------------------------

    if (
        detect_column_count(
            usable_blocks
        )
        == 1
    ):
        return sorted(
            usable_blocks,
            key=lambda block: (
                round(
                    block.y0,
                    1,
                ),
                round(
                    block.x0,
                    1,
                ),
                block.block_index,
            ),
        )

    # --------------------------------------------------------
    # Two-column page
    # --------------------------------------------------------

    page_width = (
        usable_blocks[0]
        .page_width
    )

    midpoint = (
        page_width / 2
    )

    full_width: list[
        RawBlock
    ] = []

    left_column: list[
        RawBlock
    ] = []

    right_column: list[
        RawBlock
    ] = []

    for block in usable_blocks:

        block_width = (
            block.x1
            - block.x0
        )

        block_centre = (
            block.x0
            + block.x1
        ) / 2

        if (
            block_width
            >= page_width * 0.70
        ):
            full_width.append(
                block
            )

        elif (
            block_centre
            < midpoint
        ):
            left_column.append(
                block
            )

        else:
            right_column.append(
                block
            )

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
        or [
            float("inf")
        ]
    )

    top_full_width = [
        block
        for block in full_width
        if block.y0
        <= first_column_y
    ]

    lower_full_width = [
        block
        for block in full_width
        if block
        not in top_full_width
    ]

    return (
        top_full_width
        + left_column
        + right_column
        + lower_full_width
    )


# ============================================================
# Heading detection
# ============================================================


def is_likely_heading(
    block: RawBlock,
    body_font_size: float,
) -> bool:
    """
    Detect probable section headings using wording and typography.
    """

    text = flatten_block_text(
        block.text
    )

    words = text.split()

    if not (
        1
        <= len(words)
        <= 16
    ):
        return False

    if len(text) > 160:
        return False

    # Normal prose usually ends with punctuation.
    if text.endswith(
        (
            ".",
            ",",
            ";",
        )
    ):
        return False

    # Numeric / financial fragments should not become headings.
    if re.fullmatch(
        r"[\d\s./%₦N$€£|–—-]+",
        text,
    ):
        return False

    lowered = (
        text.lower()
    )

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


# ============================================================
# Contents-page filtering
# ============================================================


def is_contents_page(
    blocks: list[RawBlock],
) -> bool:
    """
    Identify contents/index pages.

    Contents pages often create noisy retrieval matches because
    they contain many section names without substantive content.
    """

    text = "\n".join(
        block.text
        for block in blocks
    )

    lowered = (
        text.lower()
    )

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


# ============================================================
# Paragraph-boundary detection
# ============================================================


def blocks_are_in_same_column(
    previous: RawBlock,
    current: RawBlock,
) -> bool:
    """
    Check whether two consecutive blocks substantially overlap
    horizontally.
    """

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
    """
    Detect numbered, lettered and bulleted paragraph starts.

    Examples:
        1. Text
        2.1 Text
        A) Text
        • Text
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
    Determine whether the current layout block begins a new
    narrative paragraph.
    """

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

    # Moving between columns strongly suggests a new paragraph.
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

    if (
        vertical_gap
        > gap_threshold
    ):
        return True

    if starts_like_new_paragraph(
        current_text
    ):
        return True

    # Completed sentence / clause followed by another block.
    if previous_text.endswith(
        (
            ".",
            "?",
            "!",
            ":",
        )
    ):
        return True

    return False


# ============================================================
# Long-paragraph splitting
# ============================================================


def split_oversized_paragraph(
    paragraph: str,
) -> list[str]:
    """
    Split unusually long reconstructed paragraphs.

    Sentence boundaries are preferred. A word-based fallback is
    used when sentence boundaries cannot be identified.
    """

    words = (
        paragraph.split()
    )

    if (
        len(words)
        <= MAX_PARAGRAPH_WORDS
    ):
        return [
            paragraph
        ]

    sentences = [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+",
            paragraph,
        )
        if sentence.strip()
    ]

    # --------------------------------------------------------
    # No useful sentence boundaries
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Sentence-aware splitting
    # --------------------------------------------------------

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
            " ".join(
                current
            )
        )

    return output


# ============================================================
# Paragraph reconstruction
# ============================================================


def reconstruct_paragraphs(
    ordered_blocks: list[RawBlock],
    body_font_size: float,
    current_section: str | None,
) -> tuple[
    list[str],
    str | None,
]:
    """
    Convert ordered narrative blocks into coherent paragraphs.

    Headings update section metadata but are not duplicated inside
    paragraph text because section_title is stored separately.
    """

    paragraphs: list[str] = []

    current_parts: list[str] = []

    previous_content_block: (
        RawBlock
        | None
    ) = None

    def flush_current() -> None:
        """
        Finalize the paragraph currently being constructed.
        """

        nonlocal current_parts

        if not current_parts:
            return

        paragraph = (
            normalize_text(
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

        # ----------------------------------------------------
        # Heading
        # ----------------------------------------------------

        if is_likely_heading(
            block,
            body_font_size,
        ):

            flush_current()

            current_section = (
                text
            )

            previous_content_block = (
                None
            )

            continue

        # ----------------------------------------------------
        # New paragraph
        # ----------------------------------------------------

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

    return (
        paragraphs,
        current_section,
    )


# ============================================================
# Page construction
# ============================================================


def build_page(
    blocks: list[RawBlock],
    current_section: str | None,
) -> tuple[
    ProcessedPage | None,
    str | None,
]:
    """
    Reconstruct one PDF page into narrative paragraphs.

    Table blocks are expected to have already been removed by
    pdf_reader.read_pdf_blocks().
    """

    if not blocks:
        return (
            None,
            current_section,
        )

    # Exclude contents/index pages from RAG.
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

    # --------------------------------------------------------
    # Estimate page body font
    # --------------------------------------------------------

    font_sizes = [
        block.median_font_size
        for block in ordered
        if (
            block.median_font_size
            > 0
        )
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

    # --------------------------------------------------------
    # Reconstruct paragraphs
    # --------------------------------------------------------

    (
        paragraphs,
        current_section,
    ) = reconstruct_paragraphs(
        ordered_blocks=ordered,
        body_font_size=(
            body_font_size
        ),
        current_section=(
            current_section
        ),
    )

    # --------------------------------------------------------
    # Final paragraph filtering
    # --------------------------------------------------------

    paragraphs = [
        paragraph
        for paragraph in paragraphs
        if (
            len(
                paragraph.split()
            )
            >= 2
            and not is_noise_paragraph(
                paragraph
            )
        )
    ]

    total_words = sum(
        len(
            paragraph.split()
        )
        for paragraph in paragraphs
    )

    # Do not create nearly empty narrative pages.
    if total_words < 10:

        return (
            None,
            current_section,
        )

    # --------------------------------------------------------
    # Important:
    #
    # contains_table is now always False because table regions
    # are excluded upstream and stored separately in report_tables.
    # --------------------------------------------------------

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
            contains_table=False,
        ),
        current_section,
    )


# ============================================================
# Whole-document reconstruction
# ============================================================


def reconstruct_document_pages(
    pages: list[
        list[RawBlock]
    ],
) -> list[ProcessedPage]:
    """
    Reconstruct all usable narrative pages in one PDF.

    Input:
        narrative RawBlock objects from pdf_reader.py

    Output:
        ProcessedPage objects ready for paragraph-aware chunking
    """

    processed_pages: list[
        ProcessedPage
    ] = []

    current_section: (
        str
        | None
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
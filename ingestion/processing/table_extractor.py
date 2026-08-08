from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

import pymupdf

from ingestion.processing.models import (
    ReportRecord,
)


logger = logging.getLogger(__name__)


# ============================================================
# Cleaning
# ============================================================


def clean_cell(
    value: Any,
) -> str:
    """
    Normalize one extracted PDF table cell.
    """

    if value is None:
        return ""

    text = str(value)

    text = text.replace("\u00a0", " ")
    text = text.replace("\u00ad", "")
    text = text.replace("￾", "")

    # Rejoin words broken across PDF lines.
    text = re.sub(
        r"(?<=\w)-\s*\n\s*(?=\w)",
        "",
        text,
    )

    # Flatten visual line wrapping inside the cell.
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def clean_matrix(
    matrix: list[list[Any]],
) -> list[list[str]]:
    """
    Clean cells and discard completely empty rows.
    """

    cleaned: list[list[str]] = []

    for row in matrix:
        cleaned_row = [
            clean_cell(cell)
            for cell in row
        ]

        if any(cleaned_row):
            cleaned.append(
                cleaned_row
            )

    return cleaned


def normalize_matrix_width(
    matrix: list[list[str]],
) -> list[list[str]]:
    """
    Ensure every extracted row has the same number of columns.
    """

    if not matrix:
        return []

    column_count = max(
        len(row)
        for row in matrix
    )

    return [
        row
        + [""] * (
            column_count - len(row)
        )
        for row in matrix
    ]


# ============================================================
# Headers
# ============================================================


def make_unique_headers(
    headers: list[str],
) -> list[str]:
    """
    Generate unique column names.

    Duplicate names such as:

        Increase/(Decrease)
        Increase/(Decrease)

    become:

        Increase/(Decrease)
        Increase/(Decrease)_2
    """

    output: list[str] = []
    counts: dict[str, int] = {}

    for index, raw_header in enumerate(
        headers,
        start=1,
    ):
        header = clean_cell(
            raw_header
        )

        base = (
            header
            if header
            else f"column_{index}"
        )

        counts[base] = (
            counts.get(base, 0)
            + 1
        )

        occurrence = counts[base]

        if occurrence == 1:
            output.append(base)
        else:
            output.append(
                f"{base}_{occurrence}"
            )

    return output


def get_table_headers(
    table,
    matrix: list[list[str]],
) -> list[str]:
    """
    Prefer PyMuPDF detected headers.

    Fall back to the first table row.
    """

    detected: list[str] = []

    try:
        detected = [
            clean_cell(value)
            for value in (
                table.header.names
                or []
            )
        ]

    except Exception:
        detected = []

    if detected and any(detected):
        return make_unique_headers(
            detected
        )

    if matrix:
        return make_unique_headers(
            matrix[0]
        )

    return []


# ============================================================
# Table titles
# ============================================================


def get_nearby_table_title(
    page: pymupdf.Page,
    table_bbox,
) -> str | None:
    """
    Find a short text block immediately above the detected table.
    """

    table_x0 = float(
        table_bbox[0]
    )

    table_y0 = float(
        table_bbox[1]
    )

    table_x1 = float(
        table_bbox[2]
    )

    candidates: list[
        tuple[float, str]
    ] = []

    for block in page.get_text(
        "blocks",
        sort=False,
    ):
        x0 = float(block[0])
        y1 = float(block[3])
        x1 = float(block[2])

        text = clean_cell(
            block[4]
        )

        if not text:
            continue

        if y1 > table_y0:
            continue

        distance = (
            table_y0 - y1
        )

        if distance > 120:
            continue

        overlap = max(
            0.0,
            min(
                x1,
                table_x1,
            )
            - max(
                x0,
                table_x0,
            ),
        )

        if overlap <= 0:
            continue

        if len(
            text.split()
        ) > 20:
            continue

        candidates.append(
            (
                distance,
                text,
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0]
    )

    return candidates[0][1]


def infer_title_from_rows(
    matrix: list[list[str]],
) -> str | None:
    """
    Detect section/table titles embedded inside the table itself.
    """

    keywords = (
        "major ",
        "statement",
        "income",
        "financial position",
        "cash flow",
        "revenue",
        "performance",
        "segment",
        "capital",
        "assets",
        "liabilities",
        "equity",
    )

    for row in matrix[:12]:

        non_empty = [
            cell
            for cell in row
            if cell
        ]

        if len(non_empty) != 1:
            continue

        candidate = (
            non_empty[0]
        )

        lowered = (
            candidate.lower()
        )

        if any(
            keyword in lowered
            for keyword in keywords
        ):
            return candidate

    return None


# ============================================================
# Quality filtering
# ============================================================


def count_non_empty_cells(
    matrix: list[list[str]],
) -> int:
    return sum(
        bool(cell)
        for row in matrix
        for cell in row
    )


def is_useful_table(
    matrix: list[list[str]],
) -> bool:
    """
    Reject tiny false-positive tables.
    """

    if len(matrix) < 2:
        return False

    column_count = max(
        len(row)
        for row in matrix
    )

    if column_count < 2:
        return False

    if (
        count_non_empty_cells(matrix)
        < 4
    ):
        return False

    return True


# ============================================================
# JSON representation
# ============================================================


def matrix_to_json_structure(
    *,
    headers: list[str],
    matrix: list[list[str]],
) -> dict:
    """
    Convert the extracted matrix into a clean JSON structure.

    Returns:

        {
            "headers": [...],
            "rows": [
                {
                    "Metric": "...",
                    "Group Dec-23": "...",
                    ...
                }
            ]
        }
    """

    rows: list[
        dict[str, str]
    ] = []

    for matrix_row in matrix:

        row_object: dict[
            str,
            str,
        ] = {}

        for index, value in enumerate(
            matrix_row
        ):
            if index < len(headers):
                key = headers[index]
            else:
                key = (
                    f"column_{index + 1}"
                )

            row_object[key] = value

        # Do not keep completely empty rows.
        if any(
            row_object.values()
        ):
            rows.append(
                row_object
            )

    return {
        "headers": headers,
        "rows": rows,
    }


# ============================================================
# RAG representation
# ============================================================


def matrix_to_rag_text(
    *,
    title: str | None,
    headers: list[str],
    matrix: list[list[str]],
    ticker: str,
    report_year: int,
    page_number: int,
) -> str:
    """
    Convert table information into explicit text suitable for
    embeddings and LLM context.
    """

    output = [
        f"Company: {ticker}",
        f"Reporting year: {report_year}",
        f"PDF page: {page_number}",
    ]

    if title:
        output.append(
            f"Table: {title}"
        )

    output.append("")

    for row in matrix:

        non_empty = [
            value
            for value in row
            if value
        ]

        if not non_empty:
            continue

        row_label = (
            non_empty[0]
        )

        output.append(
            f"Metric: {row_label}"
        )

        for index, value in enumerate(
            row
        ):
            if not value:
                continue

            if (
                index == 0
                and value == row_label
            ):
                continue

            if index < len(headers):
                column = headers[index]
            else:
                column = (
                    f"column_{index + 1}"
                )

            output.append(
                f"{column}: {value}"
            )

        output.append("")

    return "\n".join(
        output
    ).strip()


# ============================================================
# Stable IDs
# ============================================================


def make_table_id(
    *,
    report_id: str,
    page_number: int,
    table_index: int,
    matrix: list[list[str]],
) -> str:

    serialized = json.dumps(
        matrix,
        ensure_ascii=False,
    )

    digest = hashlib.sha256(
        (
            f"{report_id}|"
            f"{page_number}|"
            f"{table_index}|"
            f"{serialized}"
        ).encode(
            "utf-8"
        )
    ).hexdigest()[:16]

    return (
        f"{report_id}_"
        f"p{page_number:04d}_"
        f"table_{table_index:02d}_"
        f"{digest}"
    )


# ============================================================
# PyMuPDF detection
# ============================================================


def detect_page_tables(
    page: pymupdf.Page,
) -> list:
    """
    Fast line-based table detection.
    """

    try:

        finder = page.find_tables(
            strategy="lines",
        )

        return list(
            finder.tables
        )

    except Exception as exc:

        logger.warning(
            "Table detection failed "
            "on page %d: %s",
            page.number + 1,
            exc,
        )

        return []


# ============================================================
# Single report
# ============================================================


def extract_tables_from_report(
    report: ReportRecord,
) -> list[dict]:
    """
    Extract structured tables from one PDF.

    Returns one dictionary per detected table.
    """

    extracted_tables: list[
        dict
    ] = []

    logger.info(
        "Processing tables: %s %d (%s)",
        report.ticker,
        report.report_year,
        report.file_path.name,
    )

    with pymupdf.open(
        report.file_path
    ) as document:

        total_pages = len(
            document
        )

        for page_index, page in enumerate(
            document
        ):

            page_number = (
                page_index + 1
            )

            logger.info(
                "%s %d | page %d/%d",
                report.ticker,
                report.report_year,
                page_number,
                total_pages,
            )

            detected_tables = (
                detect_page_tables(
                    page
                )
            )

            if detected_tables:

                logger.info(
                    "Found %d candidate table(s)",
                    len(detected_tables),
                )

            for (
                table_index,
                table,
            ) in enumerate(
                detected_tables,
                start=1,
            ):

                try:

                    matrix = (
                        table.extract()
                    )

                except Exception as exc:

                    logger.warning(
                        "Could not extract table %d "
                        "on page %d: %s",
                        table_index,
                        page_number,
                        exc,
                    )

                    continue

                matrix = clean_matrix(
                    matrix
                )

                matrix = (
                    normalize_matrix_width(
                        matrix
                    )
                )

                if not is_useful_table(
                    matrix
                ):
                    continue

                column_count = max(
                    len(row)
                    for row in matrix
                )

                headers = (
                    get_table_headers(
                        table,
                        matrix,
                    )
                )

                if (
                    len(headers)
                    < column_count
                ):

                    headers.extend(
                        [
                            f"column_{index}"
                            for index in range(
                                len(headers) + 1,
                                column_count + 1,
                            )
                        ]
                    )

                elif (
                    len(headers)
                    > column_count
                ):

                    headers = (
                        headers[
                            :column_count
                        ]
                    )

                title = (
                    infer_title_from_rows(
                        matrix
                    )
                    or get_nearby_table_title(
                        page,
                        table.bbox,
                    )
                )

                table_data = (
                    matrix_to_json_structure(
                        headers=headers,
                        matrix=matrix,
                    )
                )

                rag_text = (
                    matrix_to_rag_text(
                        title=title,
                        headers=headers,
                        matrix=matrix,
                        ticker=(
                            report.ticker
                        ),
                        report_year=(
                            report.report_year
                        ),
                        page_number=(
                            page_number
                        ),
                    )
                )

                table_id = (
                    make_table_id(
                        report_id=(
                            report.report_id
                        ),
                        page_number=(
                            page_number
                        ),
                        table_index=(
                            table_index
                        ),
                        matrix=matrix,
                    )
                )

                extracted_tables.append(
                    {
                        "table_id": table_id,
                        "report_id": (
                            report.report_id
                        ),
                        "ticker": (
                            report.ticker
                        ),
                        "report_year": (
                            report.report_year
                        ),
                        "pdf_page_number": (
                            page_number
                        ),
                        "table_index": (
                            table_index
                        ),
                        "table_title": (
                            title
                        ),
                        "row_count": (
                            len(matrix)
                        ),
                        "column_count": (
                            column_count
                        ),

                        # IMPORTANT:
                        # This is a Python dictionary.
                        # Do NOT json.dumps() it.
                        "table_data": (
                            table_data
                        ),

                        # RAG-friendly representation.
                        "rag_text": (
                            rag_text
                        ),

                        "character_count": (
                            len(rag_text)
                        ),

                        "word_count": (
                            len(
                                rag_text.split()
                            )
                        ),

                        "text_sha256": (
                            hashlib.sha256(
                                rag_text.encode(
                                    "utf-8"
                                )
                            ).hexdigest()
                        ),
                    }
                )

    logger.info(
        "Completed %s %d: "
        "%d extracted table(s).",
        report.ticker,
        report.report_year,
        len(extracted_tables),
    )

    return extracted_tables


# ============================================================
# All reports
# ============================================================


def extract_tables_from_all_reports(
    reports: list[ReportRecord],
) -> list[dict]:

    all_tables: list[
        dict
    ] = []

    total_reports = len(
        reports
    )

    for index, report in enumerate(
        reports,
        start=1,
    ):

        logger.info(
            "Report %d/%d",
            index,
            total_reports,
        )

        tables = (
            extract_tables_from_report(
                report
            )
        )

        all_tables.extend(
            tables
        )

    logger.info(
        "Finished all reports: "
        "%d extracted table(s).",
        len(all_tables),
    )

    return all_tables
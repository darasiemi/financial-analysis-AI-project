from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

import pymupdf

from ingestion.processing.models import ReportRecord


logger = logging.getLogger(__name__)


# ============================================================
# Cell cleaning
# ============================================================


def clean_cell(
    value: Any,
) -> str:
    """
    Normalize one extracted table cell.
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

    # Flatten remaining whitespace.
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
    Clean all table cells and remove completely empty rows.
    """

    cleaned: list[list[str]] = []

    for row in matrix:
        cleaned_row = [
            clean_cell(cell)
            for cell in row
        ]

        if any(cleaned_row):
            cleaned.append(cleaned_row)

    return cleaned


def normalize_matrix_width(
    matrix: list[list[str]],
) -> list[list[str]]:
    """
    Ensure every row has the same number of columns.
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
            column_count
            - len(row)
        )
        for row in matrix
    ]


# ============================================================
# Malformed-row repair
# ============================================================


VALUE_PATTERN = re.compile(
    r"""
    (?<!\S)
    (
        # Numeric values:
        # 609,308
        # 184.5%
        # (0.1%)
        # ₦1,186.47
        \(?
        [-–—]?
        (?:₦|N|\$|£|€)?
        \d[\d,]*
        (?:\.\d+)?
        %?
        \)?
        |
        # Missing values
        [-–—]
        |
        N/?A
    )
    (?!\S)
    """,
    re.VERBOSE | re.IGNORECASE,
)


def repair_collapsed_row(
    row: list[str],
    expected_columns: int,
) -> list[str]:
    """
    Repair rows where PyMuPDF collapsed the whole row into the
    first cell.

    Example:

        [
            "Profit before income tax 609,308 214,154 "
            "184.5% 107,984 88,605 21.9%",
            "",
            "",
            "",
            "",
            "",
            "",
        ]

    becomes:

        [
            "Profit before income tax",
            "609,308",
            "214,154",
            "184.5%",
            "107,984",
            "88,605",
            "21.9%",
        ]
    """

    if expected_columns <= 1:
        return row

    normalized = (
        row[:expected_columns]
        + [""] * max(
            0,
            expected_columns
            - len(row),
        )
    )

    first_cell = (
        normalized[0].strip()
    )

    if not first_cell:
        return normalized

    # Only repair rows where every other cell is empty.
    if any(
        cell.strip()
        for cell in normalized[1:]
    ):
        return normalized

    expected_values = (
        expected_columns - 1
    )

    matches = list(
        VALUE_PATTERN.finditer(
            first_cell
        )
    )

    if len(matches) < expected_values:
        return normalized

    # Use the last N values because the left side is expected
    # to contain the row label.
    value_matches = matches[
        -expected_values:
    ]

    first_value_start = (
        value_matches[0].start()
    )

    label = (
        first_cell[
            :first_value_start
        ]
        .strip()
    )

    if not label:
        return normalized

    trailing_text = (
        first_cell[
            first_value_start:
        ]
        .strip()
    )

    values = [
        match.group(1).strip()
        for match in value_matches
    ]

    reconstructed_values = (
        " ".join(values)
    )

    normalized_trailing = re.sub(
        r"\s+",
        " ",
        trailing_text,
    )

    normalized_reconstructed = re.sub(
        r"\s+",
        " ",
        reconstructed_values,
    )

    # Only repair when the trailing portion consists exactly
    # of the expected value tokens.
    if (
        normalized_trailing
        != normalized_reconstructed
    ):
        return normalized

    return [
        label,
        *values,
    ]


def repair_table_rows(
    matrix: list[list[str]],
) -> list[list[str]]:
    """
    Repair malformed collapsed rows across a table.
    """

    if not matrix:
        return []

    expected_columns = max(
        len(row)
        for row in matrix
    )

    repaired: list[
        list[str]
    ] = []

    for row in matrix:
        repaired.append(
            repair_collapsed_row(
                row=row,
                expected_columns=(
                    expected_columns
                ),
            )
        )

    return repaired


# ============================================================
# Header handling
# ============================================================


def make_unique_headers(
    headers: list[str],
) -> list[str]:
    """
    Ensure every column name is unique.
    """

    result: list[str] = []
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
            result.append(base)
        else:
            result.append(
                f"{base}_{occurrence}"
            )

    return result


def get_table_headers(
    table,
    matrix: list[list[str]],
) -> list[str]:
    """
    Prefer PyMuPDF-detected table headers.
    Fall back to the first extracted row.
    """

    detected_headers: list[str] = []

    try:
        detected_headers = [
            clean_cell(value)
            for value in (
                table.header.names
                or []
            )
        ]
    except Exception:
        detected_headers = []

    if (
        detected_headers
        and any(detected_headers)
    ):
        return make_unique_headers(
            detected_headers
        )

    if matrix:
        return make_unique_headers(
            matrix[0]
        )

    return []


def remove_repeated_header_row(
    matrix: list[list[str]],
    headers: list[str],
) -> list[list[str]]:
    """
    Remove the first matrix row when it effectively duplicates
    the detected header.
    """

    if not matrix:
        return matrix

    first_row = matrix[0]

    if (
        len(first_row)
        != len(headers)
    ):
        return matrix

    matches = 0
    comparable = 0

    for cell, header in zip(
        first_row,
        headers,
    ):
        cell_normalized = re.sub(
            r"\s+",
            " ",
            cell.strip().lower(),
        )

        header_normalized = re.sub(
            r"\s+",
            " ",
            header.strip().lower(),
        )

        # Ignore generated names such as column_1 when
        # determining whether a header is duplicated.
        if (
            header_normalized.startswith(
                "column_"
            )
            and not cell_normalized
        ):
            continue

        comparable += 1

        if (
            cell_normalized
            == header_normalized
        ):
            matches += 1

    if (
        comparable > 0
        and matches / comparable
        >= 0.80
    ):
        return matrix[1:]

    return matrix


def make_semantic_first_header(
    headers: list[str],
) -> list[str]:
    """
    Rename a generated first-column heading to 'Metric'.

    This is useful for most financial tables where the first
    column contains row labels such as:
        Gross earnings
        Profit before income tax
        Total assets
    """

    if (
        headers
        and headers[0].startswith(
            "column_"
        )
    ):
        headers = list(headers)
        headers[0] = "Metric"

    return headers


# ============================================================
# Table title detection
# ============================================================


def get_nearby_table_title(
    page: pymupdf.Page,
    table_bbox,
) -> str | None:
    """
    Find a probable title immediately above the table.
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
        x1 = float(block[2])
        y1 = float(block[3])

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
    Detect a likely table title or subsection title embedded
    inside the table.
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
    Reject obviously tiny or invalid table detections.
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
        count_non_empty_cells(
            matrix
        )
        < 4
    ):
        return False

    return True


# ============================================================
# JSON storage representation
# ============================================================


def matrix_to_json_structure(
    *,
    headers: list[str],
    matrix: list[list[str]],
) -> dict:
    """
    Convert the table into a JSON-friendly structure.

    Example:

    {
        "headers": [...],
        "rows": [
            {
                "Metric": "Gross earnings",
                "Group Dec-23 N'million": "1,186,465"
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
    Convert table data into explicit text suitable for
    embeddings and LLM context.
    """

    output: list[str] = [
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
        if not any(row):
            continue

        row_label = (
            row[0].strip()
            if row
            else ""
        )

        if row_label:
            output.append(
                f"Metric: {row_label}"
            )
        else:
            output.append(
                "Table row:"
            )

        for index, value in enumerate(
            row
        ):
            if not value:
                continue

            # First cell has already been used as the metric.
            if (
                index == 0
                and row_label
            ):
                continue

            if index < len(headers):
                column_name = (
                    headers[index]
                )
            else:
                column_name = (
                    f"column_{index + 1}"
                )

            output.append(
                f"{column_name}: {value}"
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
    """
    Create a deterministic table identifier.
    """

    serialized = json.dumps(
        matrix,
        ensure_ascii=False,
        sort_keys=False,
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
# PyMuPDF table detection
# ============================================================


def detect_page_tables(
    page: pymupdf.Page,
) -> list:
    """
    Detect tables using PyMuPDF's fast line-based strategy.
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
# Single-report extraction
# ============================================================


def extract_tables_from_report(
    report: ReportRecord,
) -> list[dict]:
    """
    Extract structured tables from one annual-report PDF.
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
                    raw_matrix = (
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

                # --------------------------------------------
                # 1. Basic cleaning
                # --------------------------------------------

                matrix = clean_matrix(
                    raw_matrix
                )

                matrix = (
                    normalize_matrix_width(
                        matrix
                    )
                )

                if not matrix:
                    continue

                # --------------------------------------------
                # 2. Repair collapsed rows
                # --------------------------------------------

                matrix = (
                    repair_table_rows(
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

                # --------------------------------------------
                # 3. Headers
                # --------------------------------------------

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

                headers = (
                    make_semantic_first_header(
                        headers
                    )
                )

                # --------------------------------------------
                # 4. Remove duplicated header row
                # --------------------------------------------

                matrix = (
                    remove_repeated_header_row(
                        matrix,
                        headers,
                    )
                )

                if not matrix:
                    continue

                # --------------------------------------------
                # 5. Table title
                # --------------------------------------------

                title = (
                    infer_title_from_rows(
                        matrix
                    )
                    or get_nearby_table_title(
                        page,
                        table.bbox,
                    )
                )

                # --------------------------------------------
                # 6. Structured JSON
                # --------------------------------------------

                table_data = (
                    matrix_to_json_structure(
                        headers=headers,
                        matrix=matrix,
                    )
                )

                # --------------------------------------------
                # 7. RAG-friendly text
                # --------------------------------------------

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

                # --------------------------------------------
                # 8. Stable ID
                # --------------------------------------------

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

                # --------------------------------------------
                # 9. Final record
                # --------------------------------------------

                extracted_tables.append(
                    {
                        "table_id": (
                            table_id
                        ),
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

                        # Native dict.
                        # dlt stores this as JSON.
                        "table_data": (
                            table_data
                        ),

                        # For embeddings / semantic retrieval.
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
# All-report extraction
# ============================================================


def extract_tables_from_all_reports(
    reports: list[ReportRecord],
) -> list[dict]:
    """
    Extract tables from all annual-report PDFs.
    """

    all_tables: list[
        dict
    ] = []

    total_reports = len(
        reports
    )

    for (
        report_index,
        report,
    ) in enumerate(
        reports,
        start=1,
    ):
        logger.info(
            "Report %d/%d",
            report_index,
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
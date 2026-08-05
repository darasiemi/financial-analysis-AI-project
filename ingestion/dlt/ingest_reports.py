from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Iterator

import dlt
import pymupdf
from dotenv import load_dotenv


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

PIPELINE_NAME = "financial_reports_pipeline"
DATASET_NAME = "financial_analysis"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    """Return the SHA-256 checksum of a file."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def parse_report_path(path: Path) -> tuple[str, int]:
    """
    Extract ticker and report year from this expected structure:

    data/<ticker>/<year>/<filename>.pdf
    """

    try:
        ticker = path.parent.parent.name.upper()
        report_year = int(path.parent.name)
    except (ValueError, IndexError) as exc:
        raise ValueError(
            f"Unexpected report path structure: {path}. "
            "Expected data/<ticker>/<year>/<filename>.pdf"
        ) from exc

    return ticker, report_year


def make_report_id(
    ticker: str,
    report_year: int,
    path: Path,
) -> str:
    """Create a stable identifier for each report file."""

    return (
        f"{ticker}_{report_year}_{path.stem}"
        .lower()
        .replace(" ", "_")
    )


def get_pdf_files() -> list[Path]:
    """Return all PDF files under the data directory."""

    if not DATA_DIR.exists():
        raise FileNotFoundError(
            f"Data directory does not exist: {DATA_DIR}"
        )

    pdf_files = sorted(DATA_DIR.rglob("*.pdf"))

    if not pdf_files:
        raise FileNotFoundError(
            f"No PDF files were found under: {DATA_DIR}"
        )

    return pdf_files


# -------------------------------------------------------------------
# dlt resources
# -------------------------------------------------------------------

@dlt.resource(
    name="reports",
    write_disposition="merge",
    primary_key="report_id",
)
def reports_resource() -> Iterator[dict]:
    """
    Yield one metadata record per PDF report.
    """

    for path in get_pdf_files():
        try:
            ticker, report_year = parse_report_path(path)
            report_id = make_report_id(
                ticker=ticker,
                report_year=report_year,
                path=path,
            )

            with pymupdf.open(path) as document:
                page_count = document.page_count

            yield {
                "report_id": report_id,
                "ticker": ticker,
                "report_year": report_year,
                "filename": path.name,
                "file_path": str(path.resolve()),
                "file_size_bytes": path.stat().st_size,
                "page_count": page_count,
                "sha256": sha256_file(path),
                "processing_status": "downloaded",
            }

        except Exception as exc:
            logger.exception(
                "Failed to read report metadata for %s: %s",
                path,
                exc,
            )


@dlt.resource(
    name="report_pages",
    write_disposition="merge",
    primary_key=[
        "report_id",
        "page_number",
    ],
)
def report_pages_resource() -> Iterator[dict]:
    """
    Extract and yield page-level text from each PDF.
    """

    for path in get_pdf_files():
        try:
            ticker, report_year = parse_report_path(path)

            report_id = make_report_id(
                ticker=ticker,
                report_year=report_year,
                path=path,
            )

            with pymupdf.open(path) as document:
                total_pages = document.page_count

                for page_index, page in enumerate(
                    document,
                    start=1,
                ):
                    text = page.get_text("text").strip()

                    yield {
                        "report_id": report_id,
                        "ticker": ticker,
                        "report_year": report_year,
                        "page_number": page_index,
                        "total_pages": total_pages,
                        "text": text,
                        "character_count": len(text),
                        "has_text": bool(text),
                    }

        except Exception as exc:
            logger.exception(
                "Failed to extract pages from %s: %s",
                path,
                exc,
            )


# -------------------------------------------------------------------
# Pipeline
# -------------------------------------------------------------------

def main() -> None:
    """
    Load report metadata and page text into PostgreSQL.
    """

    load_dotenv(PROJECT_ROOT / "ingestion" / ".env")

    # import os

    # print("Loaded:", PROJECT_ROOT / ".env")
    # print("Credentials:", os.getenv("DESTINATION__POSTGRES__CREDENTIALS"))

    pdf_files = get_pdf_files()

    logger.info(
        "Found %s PDF file(s) under %s",
        len(pdf_files),
        DATA_DIR,
    )

    pipeline = dlt.pipeline(
        pipeline_name=PIPELINE_NAME,
        destination="postgres",
        dataset_name=DATASET_NAME,
    )

    load_info = pipeline.run(
        [
            reports_resource(),
            report_pages_resource(),
        ]
    )

    print(load_info)

    logger.info(
        "Ingestion completed. PostgreSQL schema: %s",
        DATASET_NAME,
    )


if __name__ == "__main__":
    main()
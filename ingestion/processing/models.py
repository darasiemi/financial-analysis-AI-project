from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReportRecord:
    report_id: str
    ticker: str
    report_year: int
    file_path: Path


@dataclass(frozen=True)
class RawBlock:
    text: str
    page_number: int
    block_index: int

    x0: float
    y0: float
    x1: float
    y1: float

    page_width: float
    page_height: float

    max_font_size: float
    median_font_size: float
    is_bold: bool


@dataclass(frozen=True)
class ProcessedPage:
    page_number: int
    paragraphs: tuple[str, ...]
    section_title: str | None
    contains_table: bool
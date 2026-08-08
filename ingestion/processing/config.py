from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_PATH = PROJECT_ROOT / ".env"

# POSTGRES_SCHEMA = "financial_analysis"
# REPORTS_TABLE = "reports"
# REPORT_CHUNKS_TABLE = "report_chunks"
POSTGRES_SCHEMA = "financial_analysis"
REPORTS_TABLE = "reports"
REPORT_CHUNKS_TABLE = "report_chunks"
EXTRACTED_TABLES_TABLE  = "report_tables"
# EXTRACTED_TABLE_ROWS_TABLE = "report_table_rows"

PIPELINE_NAME = "financial_report_chunks_pipeline"
DATASET_NAME = "financial_analysis"


# ============================================================
# Chunking
# ============================================================

TARGET_WORDS = 400
MIN_CHUNK_WORDS = 80
OVERLAP_WORDS = 50


# ============================================================
# Repeated header/footer detection
# ============================================================

TOP_MARGIN_RATIO = 0.08
BOTTOM_MARGIN_RATIO = 0.08
MIN_REPEATED_MARGIN_PAGES = 5
REPEATED_MARGIN_RATIO = 0.25


# ============================================================
# Layout reconstruction
# ============================================================

COLUMN_GAP_RATIO = 0.08
MIN_BLOCK_WORDS = 2

# A block covering this proportion of the page width is treated
# as a full-width anchor that can separate layout regions.
FULL_WIDTH_RATIO = 0.68

# Minimum amount of text required on each side before a region
# is considered genuinely two-column.
MIN_COLUMN_WORDS = 30


# ============================================================
# Paragraph reconstruction
# ============================================================

PARAGRAPH_GAP_RATIO = 0.012
MAX_PARAGRAPH_WORDS = 180

# Table-region exclusion from narrative chunks
TABLE_BLOCK_OVERLAP_RATIO = 0.50
# ============================================================
# Decorative callout handling
# ============================================================

# Short text that is substantially larger than the body font
# may represent a pull quote, slogan, infographic label, etc.
CALLOUT_FONT_RATIO = 1.60
CALLOUT_MAX_WORDS = 15


# ============================================================
# Debugging
# ============================================================

DEBUG_PROCESSING = False
DEBUG_DIR = PROJECT_ROOT / "debug_processing"
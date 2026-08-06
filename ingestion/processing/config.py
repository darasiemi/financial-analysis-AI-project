from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_PATH = PROJECT_ROOT / ".env"

POSTGRES_SCHEMA = "financial_analysis"
REPORTS_TABLE = "reports"
REPORT_CHUNKS_TABLE = "report_chunks"

PIPELINE_NAME = "financial_report_chunks_pipeline"
DATASET_NAME = "financial_analysis"

# Chunking configuration
TARGET_WORDS = 400
MIN_CHUNK_WORDS = 80
OVERLAP_WORDS = 50

# Repeated header/footer detection
TOP_MARGIN_RATIO = 0.08
BOTTOM_MARGIN_RATIO = 0.08
MIN_REPEATED_MARGIN_PAGES = 5
REPEATED_MARGIN_RATIO = 0.25

# Layout reconstruction
COLUMN_GAP_RATIO = 0.08
MIN_BLOCK_WORDS = 2

# Paragraph reconstruction
PARAGRAPH_GAP_RATIO = 0.012
MAX_PARAGRAPH_WORDS = 180
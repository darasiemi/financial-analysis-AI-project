from __future__ import annotations

from pathlib import Path


# =============================================================
# Paths
# =============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

GENERATED_REPORTS_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "generated_reports"
)

GENERATED_REPORTS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =============================================================
# Generated file resolution
# =============================================================


def get_generated_file_path(
    filename: str,
) -> Path:
    """
    Resolve a generated report filename safely.

    Only files inside outputs/generated_reports
    may be served by the API.
    """

    safe_filename = (
        Path(filename).name
    )

    if safe_filename != filename:
        raise ValueError(
            "Invalid filename."
        )

    file_path = (
        GENERATED_REPORTS_DIR
        / safe_filename
    ).resolve()

    generated_directory = (
        GENERATED_REPORTS_DIR
        .resolve()
    )

    if (
        file_path.parent
        != generated_directory
    ):
        raise ValueError(
            "Invalid generated file path."
        )

    return file_path
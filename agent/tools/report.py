import re
from pathlib import Path
from typing import Optional

REPORTS_DIR = Path("outputs/reports")


def _safe_filename(
    value: str,
) -> str:
    """
    Convert a report title into a filesystem-safe filename.
    """

    value = value.strip().lower()

    value = re.sub(
        r"[^a-z0-9]+",
        "_",
        value,
    )

    value = value.strip("_")

    return value or "financial_report"


def create_report(
    title: str,
    executive_summary: str,
    findings: str,
    conclusion: str,
    sources: str,
    filename: Optional[str] = None,
) -> dict:
    """
    Create a Markdown financial-analysis report.

    Use this tool when the user explicitly asks for a report,
    analysis document, research summary, or written financial
    assessment.

    The report should be based only on evidence already obtained
    through the available retrieval, table, calculation, and web
    tools.

    Args:
        title:
            Report title.

        executive_summary:
            Concise summary of the main conclusions.

        findings:
            Detailed findings and financial analysis.

        conclusion:
            Final conclusion or interpretation.

        sources:
            Sources used in the analysis. Include report years,
            PDF pages, table references, or web sources where
            available.

        filename:
            Optional output filename without a directory path.

    Returns:
        Information about the generated Markdown report.
    """

    try:
        REPORTS_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        if filename:
            safe_name = _safe_filename(Path(filename).stem)
        else:
            safe_name = _safe_filename(title)

        output_path = REPORTS_DIR / f"{safe_name}.md"

        report = f"""# {title}

## Executive Summary

{executive_summary}

## Findings

{findings}

## Conclusion

{conclusion}

## Sources

{sources}
"""

        output_path.write_text(
            report,
            encoding="utf-8",
        )

        return {
            "success": True,
            "title": title,
            "format": "markdown",
            "path": str(output_path),
        }

    except Exception as exc:
        return {
            "success": False,
            "error_type": (type(exc).__name__),
            "error": str(exc),
        }

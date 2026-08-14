from typing import Any, Optional

from retrieval.hybrid import hybrid_search
from retrieval.keyword import keyword_search
from retrieval.vector import vector_search


def _make_json_safe(value: Any) -> Any:
    """
    Convert database and NumPy values into JSON-safe values.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    if isinstance(value, dict):
        return {str(key): _make_json_safe(item) for key, item in value.items()}

    if isinstance(
        value,
        (list, tuple),
    ):
        return [_make_json_safe(item) for item in value]

    if hasattr(value, "item"):
        try:
            return _make_json_safe(value.item())
        except Exception:
            pass

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return str(value)


def _compact_results(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Convert retrieval results into a compact JSON-safe form.
    """

    documents = []

    for result in results:
        document = {
            "source_id": result.get("source_id"),
            "content_type": result.get("content_type"),
            "ticker": result.get("ticker"),
            "report_year": result.get("report_year"),
            "page_start": result.get("page_start"),
            "page_end": result.get("page_end"),
            "section_title": result.get("section_title"),
            "text": result.get("text"),
            "score": result.get("score"),
            "rrf_score": result.get("rrf_score"),
        }

        documents.append(_make_json_safe(document))

    return {
        "success": True,
        "count": len(documents),
        "documents": documents,
    }


def search_keyword(
    query: str,
    ticker: Optional[str] = None,
    report_year: Optional[int] = None,
    top_k: int = 8,
) -> dict:
    """
    Search annual reports using lexical keyword retrieval.

    Args:
        query: Search query.
        ticker: Optional company ticker such as GTCO.
        report_year: Optional reporting year.
        top_k: Maximum number of results.

    Returns:
        Matching annual-report documents.
    """

    try:
        results = keyword_search(
            query,
            top_k=top_k,
            ticker=ticker,
            report_year=report_year,
        )

        return _compact_results(results)

    except Exception as exc:
        return {
            "success": False,
            "tool": "search_keyword",
            "query": query,
            "ticker": ticker,
            "report_year": report_year,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def search_semantic(
    query: str,
    ticker: Optional[str] = None,
    report_year: Optional[int] = None,
    top_k: int = 8,
) -> dict:
    """
    Search annual reports using semantic vector retrieval.

    Args:
        query: Semantic search query.
        ticker: Optional company ticker.
        report_year: Optional reporting year.
        top_k: Maximum number of results.

    Returns:
        Semantically relevant annual-report documents.
    """

    try:
        results = vector_search(
            query,
            top_k=top_k,
            ticker=ticker,
            report_year=report_year,
        )

        return _compact_results(results)

    except Exception as exc:
        return {
            "success": False,
            "tool": "search_semantic",
            "query": query,
            "ticker": ticker,
            "report_year": report_year,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def search_hybrid(
    query: str,
    ticker: Optional[str] = None,
    report_year: Optional[int] = None,
    top_k: int = 8,
) -> dict:
    """
    Search annual reports using hybrid lexical and semantic
    retrieval.

    Args:
        query: Search query.
        ticker: Optional company ticker.
        report_year: Optional reporting year.
        top_k: Maximum number of results.

    Returns:
        Ranked annual-report documents.
    """

    try:
        results = hybrid_search(
            query,
            top_k=top_k,
            ticker=ticker,
            report_year=report_year,
        )

        return _compact_results(results)

    except Exception as exc:
        return {
            "success": False,
            "tool": "search_hybrid",
            "query": query,
            "ticker": ticker,
            "report_year": report_year,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

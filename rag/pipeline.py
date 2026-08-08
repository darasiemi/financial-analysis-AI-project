from __future__ import annotations

from typing import Any

from rag.context import build_context
from rag.generator import AnswerGenerator
from retrieval.hybrid import hybrid_search
from retrieval.keyword import keyword_search
from retrieval.vector import vector_search


def retrieve_documents(
    query: str,
    *,
    mode: str,
    top_k: int,
    ticker: str | None = None,
    report_year: int | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve documents using the selected retrieval strategy.
    """

    if mode == "keyword":
        return keyword_search(
            query,
            top_k=top_k,
            ticker=ticker,
            report_year=report_year,
        )

    if mode == "vector":
        return vector_search(
            query,
            top_k=top_k,
            ticker=ticker,
            report_year=report_year,
        )

    if mode == "hybrid":
        return hybrid_search(
            query,
            top_k=top_k,
            ticker=ticker,
            report_year=report_year,
        )

    raise ValueError(
        f"Unsupported retrieval mode: {mode}"
    )


def run_rag(
    query: str,
    *,
    generator: AnswerGenerator,
    mode: str = "hybrid",
    top_k: int = 5,
    ticker: str | None = None,
    report_year: int | None = None,
) -> dict[str, Any]:
    """
    Run retrieval -> context construction -> generation.
    """

    results = retrieve_documents(
        query,
        mode=mode,
        top_k=top_k,
        ticker=ticker,
        report_year=report_year,
    )

    if not results:
        return {
            "query": query,
            "mode": mode,
            "results": [],
            "context": "",
            "answer": (
                "No relevant documents were retrieved."
            ),
        }

    context = build_context(
        results
    )

    answer = generator.generate(
        query=query,
        context=context,
    )

    return {
        "query": query,
        "mode": mode,
        "results": results,
        "context": context,
        "answer": answer,
    }
from __future__ import annotations

from retrieval.keyword import (
    keyword_search,
)
from retrieval.vector import (
    vector_search,
)


def hybrid_search(
    query: str,
    *,
    top_k: int = 10,
    candidate_k: int = 30,
    rrf_k: int = 60,
    ticker: str | None = None,
    report_year: int | None = None,
) -> list[dict]:
    """
    Combine keyword and vector rankings using Reciprocal Rank
    Fusion (RRF).
    """

    keyword_results = keyword_search(
        query,
        top_k=candidate_k,
        ticker=ticker,
        report_year=report_year,
    )

    vector_results = vector_search(
        query,
        top_k=candidate_k,
        ticker=ticker,
        report_year=report_year,
    )

    fused: dict[
        str,
        dict,
    ] = {}

    # --------------------------------------------------------
    # Keyword rankings
    # --------------------------------------------------------

    for rank, result in enumerate(
        keyword_results,
        start=1,
    ):

        document_id = result["document_id"]

        if document_id not in fused:

            fused[document_id] = {
                **result,
                "rrf_score": 0.0,
                "keyword_rank": None,
                "vector_rank": None,
            }

        fused[document_id]["keyword_rank"] = rank

        fused[document_id]["rrf_score"] += 1.0 / (rrf_k + rank)

    # --------------------------------------------------------
    # Vector rankings
    # --------------------------------------------------------

    for rank, result in enumerate(
        vector_results,
        start=1,
    ):

        document_id = result["document_id"]

        if document_id not in fused:

            fused[document_id] = {
                **result,
                "rrf_score": 0.0,
                "keyword_rank": None,
                "vector_rank": None,
            }

        fused[document_id]["vector_rank"] = rank

        fused[document_id]["rrf_score"] += 1.0 / (rrf_k + rank)

    results = sorted(
        fused.values(),
        key=lambda item: (item["rrf_score"]),
        reverse=True,
    )

    return results[:top_k]

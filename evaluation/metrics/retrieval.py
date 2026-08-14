import math


def precision_at_k(
    ranked_ids: list[str],
    relevant_ids: list[str],
    k: int,
) -> float:
    """
    Precision@k

    Measures the proportion of the top-k retrieved documents
    that are relevant.

    Example:
        retrieved top 5 = [A, B, C, D, E]
        relevant = [B, D]

        Precision@5 = 2 / 5 = 0.4
    """

    if k <= 0:
        return 0.0

    retrieved = ranked_ids[:k]

    if not retrieved:
        return 0.0

    relevant = set(relevant_ids)

    hits = sum(source_id in relevant for source_id in retrieved)

    return hits / len(retrieved)


def recall_at_k(
    ranked_ids: list[str],
    relevant_ids: list[str],
    k: int,
) -> float:
    """
    Recall@k

    Measures the proportion of all relevant documents that
    appear in the top-k retrieved documents.

    Example:
        relevant = [A, B]
        retrieved top 5 contains only A

        Recall@5 = 1 / 2 = 0.5
    """

    if k <= 0:
        return 0.0

    if not relevant_ids:
        return 0.0

    relevant = set(relevant_ids)

    retrieved = set(ranked_ids[:k])

    hits = len(relevant & retrieved)

    return hits / len(relevant)


def hit_rate_at_k(
    ranked_ids: list[str],
    relevant_ids: list[str],
    k: int,
) -> float:
    """
    Hit Rate@k

    Returns 1.0 when at least one relevant document appears
    in the top-k results, otherwise 0.0.

    When averaged over the full benchmark, this becomes:

        Hit Rate@k =
        number of queries with >= 1 relevant result in top-k
        ----------------------------------------------------
                       total number of queries
    """

    if k <= 0:
        return 0.0

    if not relevant_ids:
        return 0.0

    relevant = set(relevant_ids)

    retrieved = set(ranked_ids[:k])

    return 1.0 if relevant & retrieved else 0.0


def reciprocal_rank(
    ranked_ids: list[str],
    relevant_ids: list[str],
) -> float:
    """
    Reciprocal Rank

    Returns the reciprocal of the rank of the first relevant
    retrieved document.

    Examples:

        first relevant result at rank 1 -> 1.0
        first relevant result at rank 2 -> 0.5
        first relevant result at rank 4 -> 0.25
        no relevant result              -> 0.0

    The evaluation runner averages this value across all queries,
    producing Mean Reciprocal Rank (MRR).
    """

    if not relevant_ids:
        return 0.0

    relevant = set(relevant_ids)

    for rank, source_id in enumerate(
        ranked_ids,
        start=1,
    ):
        if source_id in relevant:
            return 1.0 / rank

    return 0.0


def ndcg_at_k(
    ranked_ids: list[str],
    relevant_ids: list[str],
    k: int,
) -> float:
    """
    Normalized Discounted Cumulative Gain at k.

    Rewards relevant documents appearing higher in the ranking.

    This implementation assumes binary relevance:

        relevant document     -> relevance = 1
        non-relevant document -> relevance = 0
    """

    if k <= 0:
        return 0.0

    if not relevant_ids:
        return 0.0

    relevant = set(relevant_ids)

    # ---------------------------------------------------------
    # Discounted Cumulative Gain
    # ---------------------------------------------------------

    dcg = 0.0

    for rank, source_id in enumerate(
        ranked_ids[:k],
        start=1,
    ):

        relevance = 1.0 if source_id in relevant else 0.0

        if relevance == 0.0:
            continue

        dcg += relevance / math.log2(rank + 1)

    # ---------------------------------------------------------
    # Ideal DCG
    # ---------------------------------------------------------

    ideal_hits = min(
        len(relevant),
        k,
    )

    if ideal_hits == 0:
        return 0.0

    idcg = sum(
        1.0 / math.log2(rank + 1)
        for rank in range(
            1,
            ideal_hits + 1,
        )
    )

    return dcg / idcg if idcg > 0 else 0.0


def retrieval_metrics(
    ranked_ids: list[str],
    relevant_ids: list[str],
    *,
    k: int,
) -> dict:
    """
    Calculate all retrieval metrics for a single query.

    The evaluation runner averages these per-query values over
    the benchmark.

    Returned metrics:

    - Precision@k
    - Recall@k
    - Hit Rate@k
    - Reciprocal Rank
    - nDCG@k

    When averaged across the benchmark:

        reciprocal_rank -> MRR
        hit_rate@k      -> benchmark Hit Rate@k
    """

    return {
        f"precision@{k}": (
            precision_at_k(
                ranked_ids,
                relevant_ids,
                k,
            )
        ),
        f"recall@{k}": (
            recall_at_k(
                ranked_ids,
                relevant_ids,
                k,
            )
        ),
        f"hit_rate@{k}": (
            hit_rate_at_k(
                ranked_ids,
                relevant_ids,
                k,
            )
        ),
        "mrr": (
            reciprocal_rank(
                ranked_ids,
                relevant_ids,
            )
        ),
        f"ndcg@{k}": (
            ndcg_at_k(
                ranked_ids,
                relevant_ids,
                k,
            )
        ),
    }

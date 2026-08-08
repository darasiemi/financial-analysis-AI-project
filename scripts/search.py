from __future__ import annotations

import argparse
import time

from retrieval.hybrid import (
    hybrid_search,
)
from retrieval.keyword import (
    keyword_search,
)
from retrieval.vector import (
    vector_search,
)


def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "query",
    )

    parser.add_argument(
        "--mode",
        choices=(
            "keyword",
            "vector",
            "hybrid",
        ),
        default="hybrid",
    )

    parser.add_argument(
        "--ticker",
    )

    parser.add_argument(
        "--year",
        type=int,
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )

    args = parser.parse_args()

    # ---------------------------------------------------------
    # Measure retrieval time only
    # ---------------------------------------------------------

    start = time.perf_counter()

    if args.mode == "keyword":

        results = keyword_search(
            args.query,
            top_k=args.top_k,
            ticker=args.ticker,
            report_year=args.year,
        )

    elif args.mode == "vector":

        results = vector_search(
            args.query,
            top_k=args.top_k,
            ticker=args.ticker,
            report_year=args.year,
        )

    else:

        results = hybrid_search(
            args.query,
            top_k=args.top_k,
            ticker=args.ticker,
            report_year=args.year,
        )

    retrieval_time = time.perf_counter() - start

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    print("\n" + "=" * 80)
    print(f"Search mode      : {args.mode}")
    print(f"Query            : {args.query}")
    print(f"Retrieved        : {len(results)} document(s)")
    print(f"Retrieval time   : {retrieval_time:.4f} seconds")
    print("=" * 80)

    # ---------------------------------------------------------
    # Results
    # ---------------------------------------------------------

    for index, result in enumerate(
        results,
        start=1,
    ):

        print("\n" + "=" * 80)

        print(f"RESULT {index}")

        print(f"Type: {result['content_type']}")
        print(f"Ticker: {result['ticker']}")
        print(f"Year: {result['report_year']}")
        print(
            f"Pages: {result['page_start']}-{result['page_end']}"
        )
        print(
            f"Section: {result['section_title']}"
        )

        if "score" in result:
            print(
                f"Score: {result['score']:.4f}"
            )

        if "rrf_score" in result:
            print(
                f"RRF Score: {result['rrf_score']:.4f}"
            )

        print()
        print(result["text"][:1500])


if __name__ == "__main__":
    main()
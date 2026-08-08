import argparse

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
        "query"
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

    for index, result in enumerate(
        results,
        start=1,
    ):

        print(
            "=" * 80
        )

        print(
            f"RESULT {index}"
        )

        print(
            f"Type: {result['content_type']}"
        )

        print(
            f"Ticker: {result['ticker']}"
        )

        print(
            f"Year: {result['report_year']}"
        )

        print(
            (
                "Pages: "
                f"{result['page_start']}"
                "-"
                f"{result['page_end']}"
            )
        )

        print(
            (
                "Section: "
                f"{result['section_title']}"
            )
        )

        print()

        print(
            result["text"][:1500]
        )


if __name__ == "__main__":
    main()
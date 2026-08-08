from __future__ import annotations

import argparse
import time

from ingestion.processing.database import (
    load_environment,
)
from rag.gemini import GeminiGenerator
from rag.pipeline import run_rag


def main() -> None:
    load_environment()
    
    parser = argparse.ArgumentParser(
        description=(
            "Test the financial-report RAG pipeline."
        )
    )

    parser.add_argument(
        "query",
        help="Question to ask.",
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
        default=None,
    )

    parser.add_argument(
        "--year",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
    )

    parser.add_argument(
        "--show-context",
        action="store_true",
    )

    args = parser.parse_args()

    load_environment()

    generator = GeminiGenerator(
        model=args.model,
    )

    start = time.perf_counter()

    result = run_rag(
        args.query,
        generator=generator,
        mode=args.mode,
        top_k=args.top_k,
        ticker=args.ticker,
        report_year=args.year,
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    if args.show_context:
        print()
        print("=" * 80)
        print("RETRIEVED CONTEXT")
        print("=" * 80)
        print(result["context"])

    print()
    print("=" * 80)
    print("ANSWER")
    print("=" * 80)
    print(result["answer"])

    print()
    print(
        f"Total RAG time: "
        f"{elapsed:.4f} seconds"
    )


if __name__ == "__main__":
    main()
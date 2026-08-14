import argparse

from evaluation.runner import (
    evaluate_pipeline,
)
from ingestion.processing.database import (
    load_environment,
)


def main() -> None:
    """
    Evaluate either the RAG or agent pipeline.

    By default, the benchmark is read from:

        data/evaluation/benchmark.jsonl

    Evaluation results are written to:

        outputs/evaluation/
    """

    parser = argparse.ArgumentParser(
        description=("Evaluate the financial-analysis " "RAG or agent pipeline.")
    )

    parser.add_argument(
        "--pipeline",
        choices=[
            "rag",
            "agent",
        ],
        required=True,
        help=("Pipeline to evaluate."),
    )

    parser.add_argument(
        "--dataset",
        default=("data/evaluation/benchmark.jsonl"),
        help=("Path to the evaluation benchmark."),
    )

    parser.add_argument(
        "--mode",
        choices=[
            "keyword",
            "vector",
            "hybrid",
        ],
        default="hybrid",
        help=("Retrieval mode used for " "RAG evaluation."),
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help=("Number of ranked retrieval " "results used for evaluation."),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=("Optional maximum number of " "benchmark examples to evaluate."),
    )

    parser.add_argument(
        "--model",
        default=None,
        help=("Optional Gemini model override " "for the evaluated pipeline."),
    )

    parser.add_argument(
        "--judge-model",
        default=None,
        help=("Optional Gemini model override " "for LLM-as-a-judge evaluation."),
    )

    parser.add_argument(
        "--output-dir",
        default=("outputs/evaluation"),
        help=("Directory where Excel evaluation " "results are written."),
    )

    args = parser.parse_args()

    # =========================================================
    # Environment
    # =========================================================

    load_environment()

    # =========================================================
    # Run evaluation
    # =========================================================

    result = evaluate_pipeline(
        dataset_path=args.dataset,
        pipeline=args.pipeline,
        retrieval_mode=args.mode,
        top_k=args.top_k,
        limit=args.limit,
        output_dir=args.output_dir,
        model=args.model,
        judge_model=args.judge_model,
    )

    # =========================================================
    # Terminal output
    # =========================================================

    print()
    print("=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)

    print(f"Pipeline: {result['pipeline']}")

    if result["retrieval_mode"] is not None:
        print("Retrieval mode: " f"{result['retrieval_mode']}")

    print(f"Dataset: {args.dataset}")

    print(f"Examples: {result['examples']}")

    print("Successful: " f"{result['successful_examples']}")

    print("Failed: " f"{result['failed_examples']}")

    print()
    print("METRICS")
    print("-" * 80)

    for metric, score in result["summary"].items():
        if isinstance(
            score,
            float,
        ):
            print(f"{metric}: {score:.4f}")
        else:
            print(f"{metric}: {score}")

    print()
    print("=" * 80)

    print("Excel results: " f"{result['excel_file']}")

    print("=" * 80)


if __name__ == "__main__":
    main()

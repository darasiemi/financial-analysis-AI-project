import argparse
import os

from evaluation.dataset import (
    save_dataset,
)
from evaluation.generate import (
    generate_dataset,
)
from ingestion.processing.database import (
    load_environment,
)


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Generate a difficult, validated "
            "financial-analysis benchmark."
        )
    )

    parser.add_argument(
        "--n",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--output",
        default=(
            "data/evaluation/"
            "benchmark.jsonl"
        ),
    )

    parser.add_argument(
        "--model",
        default=None,
    )

    parser.add_argument(
        "--validation-model",
        default=None,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--pool-size",
        type=int,
        default=2000,
    )

    parser.add_argument(
        "--minimum-quality",
        type=float,
        default=0.90,
    )

    parser.add_argument(
        "--minimum-difficulty",
        type=float,
        default=0.80,
    )

    parser.add_argument(
        "--minimum-financial-relevance",
        type=float,
        default=0.90,
    )

    parser.add_argument(
        "--max-attempt-multiplier",
        type=int,
        default=10,
    )

    args = (
        parser.parse_args()
    )

    load_environment()

    generation_model = (
        args.model
        or os.environ.get(
            "GEMINI_EVAL_GENERATOR_MODEL",
            "gemini-2.5-flash",
        )
    )

    validation_model = (
        args.validation_model
        or os.environ.get(
            "GEMINI_EVAL_VALIDATOR_MODEL",
            generation_model,
        )
    )

    examples = (
        generate_dataset(
            n=args.n,
            model=(
                generation_model
            ),
            validation_model=(
                validation_model
            ),
            seed=args.seed,
            pool_size=(
                args.pool_size
            ),
            minimum_quality=(
                args.minimum_quality
            ),
            minimum_difficulty=(
                args.minimum_difficulty
            ),
            minimum_financial_relevance=(
                args.minimum_financial_relevance
            ),
            max_attempt_multiplier=(
                args.max_attempt_multiplier
            ),
        )
    )

    save_dataset(
        examples,
        args.output,
    )

    print()
    print(
        "=" * 80
    )
    print(
        "BENCHMARK SAVED"
    )
    print(
        "=" * 80
    )

    print(
        f"Examples: {len(examples)}"
    )

    print(
        "Generation model: "
        f"{generation_model}"
    )

    print(
        "Validation model: "
        f"{validation_model}"
    )

    print(
        "Minimum quality: "
        f"{args.minimum_quality}"
    )

    print(
        "Minimum difficulty: "
        f"{args.minimum_difficulty}"
    )

    print(
        "Minimum financial relevance: "
        f"{args.minimum_financial_relevance}"
    )

    print(
        f"Output: {args.output}"
    )


if __name__ == "__main__":
    main()
from __future__ import annotations

import argparse
import os
import random
import time
import uuid

import requests


QUESTIONS = [
    # ---------------------------------------------------------
    # GTCO
    # ---------------------------------------------------------

    "What was GTCO's profit before tax in 2025?",

    "How did GTCO's profit after tax change from 2024 to 2025?",

    "What were GTCO's total assets in 2025?",

    "Who was the Group Chief Executive Officer of GTCO in 2025?",

    "Who was the Chairman of GTCO in 2025?",


    # ---------------------------------------------------------
    # Zenith Bank
    # ---------------------------------------------------------

    "What was Zenith Bank's profit before tax in 2025?",

    "How did Zenith Bank's total assets change from 2024 to 2025?",

    "What was Zenith Bank's gross earnings in 2025?",

    "Who was the Group Managing Director and CEO of Zenith Bank in 2025?",

    "Who was the Chairman of Zenith Bank in 2025?",


    # ---------------------------------------------------------
    # MTN Nigeria
    # ---------------------------------------------------------

    "What was MTN Nigeria's revenue in 2025?",

    "How did MTN Nigeria's revenue change from 2024 to 2025?",

    "What was MTN Nigeria's profit after tax in 2025?",

    "Who was the Chief Executive Officer of MTN Nigeria in 2025?",

    "Who was the Chairman of MTN Nigeria in 2025?",


    # ---------------------------------------------------------
    # Cross-company comparisons
    # ---------------------------------------------------------

    "Compare the total assets of GTCO and Zenith Bank in 2025.",

    "Compare the profit after tax of GTCO and Zenith Bank in 2025.",

    "Which of GTCO, Zenith Bank, and MTN Nigeria reported the highest revenue in 2025?",

    "Compare the revenue growth of GTCO, Zenith Bank, and MTN Nigeria from 2024 to 2025.",

    "Who were the chief executives of GTCO, Zenith Bank, and MTN Nigeria in 2025?",
]


def send_request(
    base_url: str,
    pipeline: str,
) -> None:

    question = random.choice(
        QUESTIONS
    )

    payload = {
        "question": question,
        "session_id": (
            f"synthetic-{uuid.uuid4()}"
        ),
        "pipeline": pipeline,
        "retrieval_mode": "hybrid",
        "top_k": 8,
        "ticker": None,
        "report_year": None,
        "model": "gemini-2.5-flash",
    }

    started = time.perf_counter()

    try:

        response = requests.post(
            f"{base_url}/api/v1/query",
            json=payload,
            timeout=180,
        )

        elapsed = (
            time.perf_counter()
            - started
        )

        if response.ok:

            result = response.json()

            print(
                f"✓ {pipeline.upper():5} | "
                f"{elapsed:6.2f}s | "
                f"{question}"
            )

            response_id = result.get(
                "response_id"
            )

            if response_id:

                print(
                    f"  response_id="
                    f"{response_id}"
                )

        else:

            print(
                f"✗ {pipeline.upper():5} | "
                f"HTTP {response.status_code} | "
                f"{response.text[:200]}"
            )

    except requests.RequestException as exc:

        print(
            f"✗ {pipeline.upper():5} | "
            f"{exc}"
        )


def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--requests",
        type=int,
        default=10,
        help="Number of synthetic requests.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds between requests.",
    )

    parser.add_argument(
        "--pipeline",
        choices=[
            "rag",
            "agent",
            "mixed",
        ],
        default="mixed",
    )

    args = parser.parse_args()

    base_url = os.getenv(
        "FASTAPI_BASE_URL",
        "http://localhost:8000",
    ).rstrip("/")

    print(
        f"\nSending {args.requests} "
        f"synthetic requests to {base_url}\n"
    )

    for index in range(
        args.requests
    ):

        if args.pipeline == "mixed":

            pipeline = random.choice(
                [
                    "rag",
                    "agent",
                ]
            )

        else:

            pipeline = args.pipeline

        print(
            f"[{index + 1}/{args.requests}]",
            end=" ",
        )

        send_request(
            base_url=base_url,
            pipeline=pipeline,
        )

        if (
            index
            < args.requests - 1
        ):
            time.sleep(
                args.delay
            )


if __name__ == "__main__":
    main()
from __future__ import annotations

import hashlib
import os
import time

from google import genai
from google.genai import types
from pydantic import (
    BaseModel,
    Field,
)

from monitoring.database import (
    mark_judge_failed,
    mark_judge_skipped,
    save_judge_result,
)
from monitoring.pricing import (
    estimate_cost_usd,
)


class RelevanceJudgement(
    BaseModel
):
    score: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str


def _should_sample(
    response_id: str,
) -> bool:
    """
    Deterministic sampling based on response ID.
    """

    sample_rate = float(
        os.getenv(
            "MONITORING_JUDGE_SAMPLE_RATE",
            "0.25",
        )
    )

    sample_rate = max(
        0.0,
        min(
            1.0,
            sample_rate,
        ),
    )

    digest = hashlib.sha256(
        response_id.encode(
            "utf-8"
        )
    ).hexdigest()

    value = (
        int(
            digest[:8],
            16,
        )
        / 0xFFFFFFFF
    )

    return (
        value
        < sample_rate
    )


def judge_relevance_background(
    *,
    response_id: str,
    question: str,
    answer: str,
) -> None:
    """
    Background relevance evaluation.

    Runs after the user has already received
    the application response.
    """

    if not _should_sample(
        response_id
    ):
        mark_judge_skipped(
            response_id
        )

        return

    model = os.getenv(
        "MONITORING_JUDGE_MODEL",
        "gemini-2.5-flash-lite",
    )

    prompt = f"""
You are evaluating only QUESTION-ANSWER RELEVANCE.

Do not evaluate factual correctness.
Do not evaluate faithfulness to source documents.
Do not evaluate writing style unless it affects relevance.

Question:
{question}

Answer:
{answer}

Score how directly and sufficiently the answer addresses
the user's question.

Scoring:
1.0 = directly and fully addresses the question
0.75 = mostly relevant with minor omissions
0.5 = partially relevant
0.25 = mostly irrelevant
0.0 = does not address the question
""".strip()

    try:

        client = genai.Client(
            api_key=os.environ[
                "GEMINI_API_KEY"
            ]
        )

        start = time.perf_counter()

        response = (
            client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type=(
                        "application/json"
                    ),
                    response_schema=(
                        RelevanceJudgement
                    ),
                ),
            )
        )

        latency = (
            time.perf_counter()
            - start
        )

        judgement = (
            RelevanceJudgement
            .model_validate_json(
                response.text
                or "{}"
            )
        )

        usage = getattr(
            response,
            "usage_metadata",
            None,
        )

        input_tokens = int(
            getattr(
                usage,
                "prompt_token_count",
                0,
            )
            or 0
        )

        output_tokens = int(
            getattr(
                usage,
                "candidates_token_count",
                0,
            )
            or 0
        )

        thinking_tokens = int(
            getattr(
                usage,
                "thoughts_token_count",
                0,
            )
            or 0
        )

        total_tokens = int(
            getattr(
                usage,
                "total_token_count",
                (
                    input_tokens
                    + output_tokens
                    + thinking_tokens
                ),
            )
            or 0
        )

        cost = estimate_cost_usd(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
        )

        save_judge_result(
            response_id=response_id,
            score=judgement.score,
            reason=judgement.reason,
            model=model,
            latency_seconds=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
        )

    except Exception as exc:

        mark_judge_failed(
            response_id=response_id,
            error=str(exc),
        )
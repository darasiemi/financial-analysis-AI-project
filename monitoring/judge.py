from __future__ import annotations

import hashlib
import logging
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

# =============================================================
# Logging
# =============================================================

logger = logging.getLogger(__name__)


# =============================================================
# Structured judge response
# =============================================================


class RelevanceJudgement(BaseModel):
    """
    Structured response returned by the
    relevance judge.
    """

    score: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str


# =============================================================
# Sampling
# =============================================================


def _should_sample(
    response_id: str,
) -> bool:
    """
    Determine whether a response should be evaluated.

    Sampling is deterministic based on response_id.
    The same response ID will therefore always produce
    the same sampling decision.

    MONITORING_JUDGE_SAMPLE_RATE:
        0.0 = judge no responses
        0.25 = judge approximately 25%
        1.0 = judge every response
    """

    sample_rate = float(
        os.getenv(
            "MONITORING_JUDGE_SAMPLE_RATE",
            "0.25",
        )
    )

    # Ensure sample rate stays between 0 and 1.
    sample_rate = max(
        0.0,
        min(
            1.0,
            sample_rate,
        ),
    )

    digest = hashlib.sha256(response_id.encode("utf-8")).hexdigest()

    value = (
        int(
            digest[:8],
            16,
        )
        / 0xFFFFFFFF
    )

    should_sample = value < sample_rate

    logger.info(
        (
            "Judge sampling decision: "
            "response_id=%s "
            "sample_rate=%.3f "
            "sample_value=%.6f "
            "selected=%s"
        ),
        response_id,
        sample_rate,
        value,
        should_sample,
    )

    return should_sample


# =============================================================
# Background relevance judge
# =============================================================


def judge_relevance_background(
    *,
    response_id: str,
    question: str,
    answer: str,
) -> None:
    """
    Evaluate question-answer relevance.

    This function is intended to be scheduled as a
    FastAPI background task after the main application
    response has already been returned to the user.

    The judge evaluates ONLY question-answer relevance.

    It does not evaluate:
    - factual correctness;
    - faithfulness to retrieved documents;
    - writing style, except where it affects relevance.
    """

    logger.info(
        "Relevance judge requested for response_id=%s",
        response_id,
    )

    # ---------------------------------------------------------
    # Sampling
    # ---------------------------------------------------------

    if not _should_sample(response_id):
        logger.info(
            "Relevance judge skipped for response_id=%s",
            response_id,
        )

        try:
            mark_judge_skipped(response_id)

        except Exception:
            logger.exception(
                ("Failed to mark relevance judge as " "skipped for response_id=%s"),
                response_id,
            )

        return

    # ---------------------------------------------------------
    # Configuration
    # ---------------------------------------------------------

    model = os.getenv(
        "MONITORING_JUDGE_MODEL",
        "gemini-2.5-flash-lite",
    )

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        error_message = "GEMINI_API_KEY is not configured."

        logger.error(
            ("Relevance judge configuration error " "for response_id=%s: %s"),
            response_id,
            error_message,
        )

        try:
            mark_judge_failed(
                response_id=response_id,
                error=error_message,
            )

        except Exception:
            logger.exception(
                ("Failed to record judge configuration " "failure for response_id=%s"),
                response_id,
            )

        return

    logger.info(
        ("Starting relevance judge: " "response_id=%s model=%s"),
        response_id,
        model,
    )

    # ---------------------------------------------------------
    # Prompt
    # ---------------------------------------------------------

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

Return a relevance score between 0.0 and 1.0 and a short
reason explaining the score.
""".strip()

    # ---------------------------------------------------------
    # Judge execution
    # ---------------------------------------------------------

    try:

        client = genai.Client(api_key=api_key)

        start = time.perf_counter()

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type=("application/json"),
                response_schema=(RelevanceJudgement),
            ),
        )

        latency = time.perf_counter() - start

        logger.info(
            ("Gemini relevance judge returned: " "response_id=%s " "latency=%.3fs"),
            response_id,
            latency,
        )

        # -----------------------------------------------------
        # Parse structured response
        # -----------------------------------------------------

        response_text = response.text or "{}"

        judgement = RelevanceJudgement.model_validate_json(response_text)

        logger.info(
            (
                "Relevance judgement parsed: "
                "response_id=%s "
                "score=%.3f "
                "reason=%s"
            ),
            response_id,
            judgement.score,
            judgement.reason,
        )

        # -----------------------------------------------------
        # Token usage
        # -----------------------------------------------------

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
                (input_tokens + output_tokens + thinking_tokens),
            )
            or 0
        )

        # -----------------------------------------------------
        # Judge cost
        # -----------------------------------------------------

        cost = estimate_cost_usd(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
        )

        logger.info(
            (
                "Relevance judge usage: "
                "response_id=%s "
                "input_tokens=%d "
                "output_tokens=%d "
                "thinking_tokens=%d "
                "total_tokens=%d "
                "cost_usd=%.10f"
            ),
            response_id,
            input_tokens,
            output_tokens,
            thinking_tokens,
            total_tokens,
            cost,
        )

        # -----------------------------------------------------
        # Save result
        # -----------------------------------------------------

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

        logger.info(
            (
                "Relevance judge completed successfully: "
                "response_id=%s "
                "score=%.3f "
                "latency=%.3fs "
                "cost_usd=%.10f"
            ),
            response_id,
            judgement.score,
            latency,
            cost,
        )

    # ---------------------------------------------------------
    # Failure handling
    # ---------------------------------------------------------

    except Exception as exc:

        logger.exception(
            ("Relevance judge failed for " "response_id=%s"),
            response_id,
        )

        try:
            mark_judge_failed(
                response_id=response_id,
                error=str(exc),
            )

        except Exception:
            logger.exception(
                (
                    "Failed to record relevance judge "
                    "failure in database for "
                    "response_id=%s"
                ),
                response_id,
            )

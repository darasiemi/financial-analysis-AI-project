import json
import os

from google import genai
from google.genai import types


JUDGE_PROMPT = """
Evaluate a financial question-answering system.

For each metric, return:

- score: a number from 0.0 to 1.0
- reason: a short explanation of why that score was assigned

Evaluate the following metrics:

CORRECTNESS

Compare the generated answer against the reference answer.

Check whether:
- financial values match;
- currencies match;
- units match;
- reporting periods match;
- Group and Company figures are not confused;
- important facts required by the question are correct.

FAITHFULNESS

Determine whether factual claims in the generated answer are
supported by the retrieved context.

Do not give a high faithfulness score merely because the answer
matches the reference answer.

The generated answer must be supported by the retrieved evidence.

Check for:
- unsupported financial values;
- unsupported interpretations;
- incorrect units;
- incorrect reporting periods;
- claims not present in the retrieved context.

RELEVANCE

Determine whether the generated answer directly answers the
user's question.

Check whether:
- the requested information is addressed;
- unnecessary or unrelated content is avoided;
- the answer is sufficiently complete for the question.

SCORING

Use scores between 0.0 and 1.0.

Examples:

1.0
Fully satisfies the metric.

0.75
Mostly correct/supported/relevant with a minor issue.

0.5
Partially satisfies the metric but contains an important issue.

0.25
Only a small portion satisfies the metric.

0.0
Does not satisfy the metric.

The reason should be concise and refer to observable evidence,
such as incorrect values, missing information, unsupported claims,
wrong currency, wrong year, or incomplete answers.

Do not provide private chain-of-thought reasoning.

Return JSON only in this exact structure:

{
  "correctness": {
    "score": 0.0,
    "reason": "Brief explanation."
  },
  "faithfulness": {
    "score": 0.0,
    "reason": "Brief explanation."
  },
  "relevance": {
    "score": 0.0,
    "reason": "Brief explanation."
  }
}
""".strip()


class GeminiJudge:

    def __init__(
        self,
        model: str | None = None,
    ) -> None:

        self.model = (
            model
            or os.environ.get(
                "GEMINI_EVAL_JUDGE_MODEL",
                "gemini-2.5-flash",
            )
        )

        self.client = genai.Client()

    def evaluate(
        self,
        *,
        question: str,
        reference_answer: str,
        generated_answer: str,
        contexts: list[str],
    ) -> dict:
        """
        Evaluate a generated answer against the reference answer
        and retrieved evidence.

        Returns scores and short explanations for:
        - correctness
        - faithfulness
        - relevance
        """

        context = "\n\n".join(
            contexts[:8]
        )

        # Prevent extremely large evaluation prompts.
        context = context[:24000]

        prompt = f"""
{JUDGE_PROMPT}

QUESTION
========
{question}

REFERENCE ANSWER
================
{reference_answer}

GENERATED ANSWER
================
{generated_answer}

RETRIEVED CONTEXT
=================
{context}
""".strip()

        response = (
            self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type=(
                        "application/json"
                    ),
                    temperature=0.0,
                ),
            )
        )

        if not response.text:
            raise RuntimeError(
                "Evaluation judge returned no response."
            )

        result = json.loads(
            response.text
        )

        self._validate_result(
            result
        )

        return result

    @staticmethod
    def _validate_result(
        result: dict,
    ) -> None:
        """
        Validate the structure returned by the LLM judge.
        """

        required_metrics = [
            "correctness",
            "faithfulness",
            "relevance",
        ]

        for metric in required_metrics:

            if metric not in result:
                raise ValueError(
                    f"Judge response missing metric: {metric}"
                )

            metric_result = result[
                metric
            ]

            if not isinstance(
                metric_result,
                dict,
            ):
                raise ValueError(
                    f"Judge metric '{metric}' "
                    "must be an object."
                )

            if (
                "score"
                not in metric_result
            ):
                raise ValueError(
                    f"Judge metric '{metric}' "
                    "is missing score."
                )

            if (
                "reason"
                not in metric_result
            ):
                raise ValueError(
                    f"Judge metric '{metric}' "
                    "is missing reason."
                )

            score = float(
                metric_result[
                    "score"
                ]
            )

            if not (
                0.0
                <= score
                <= 1.0
            ):
                raise ValueError(
                    f"Judge score for '{metric}' "
                    "must be between 0 and 1."
                )
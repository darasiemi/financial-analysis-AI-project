from __future__ import annotations

import os

from google import genai

from rag.generator import AnswerGenerator
from monitoring.telemetry import (
    record_gemini_response,
)


SYSTEM_PROMPT = """
You are a financial-report question-answering assistant.

Answer using only the supplied retrieved context.

Rules:
- Do not invent facts.
- If the context is insufficient, state that clearly.
- Prefer exact numeric values when available.
- Preserve currencies, units, percentages, and reporting periods.
- Distinguish Group and Company values where applicable.
- Cite supporting evidence using [SOURCE N].
- Do not cite a source that does not support the claim.
- Keep the answer concise and factual.
""".strip()


class GeminiGenerator:
    """
    Gemini implementation of the AnswerGenerator interface.
    """

    def __init__(
        self,
        *,
        model: str = "gemini-2.5-flash",
    ) -> None:
        self.model = model

        self.client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"]
        )

    def generate(
        self,
        *,
        query: str,
        context: str,
    ) -> str:
        prompt = f"""
{SYSTEM_PROMPT}

Question:
{query}

Retrieved context:
{context}
""".strip()

        response = (
            self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
        )

        record_gemini_response(
            response=response,
            model=self.model,
            purpose="rag_generation",
        )

        if response.text is None:
            raise RuntimeError(
                "Gemini returned no text response."
            )

        return response.text
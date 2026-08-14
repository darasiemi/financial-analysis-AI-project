from __future__ import annotations

from typing import Protocol


class AnswerGenerator(Protocol):
    """
    Interface for any LLM-backed answer generator.
    """

    def generate(
        self,
        *,
        query: str,
        context: str,
    ) -> str: ...

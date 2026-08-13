from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator

from monitoring.pricing import (
    estimate_cost_usd,
)


@dataclass
class LLMCall:
    purpose: str
    model: str

    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0

    estimated_cost_usd: float = 0.0


@dataclass
class RequestTelemetry:
    response_id: str

    llm_calls: list[
        LLMCall
    ] = field(
        default_factory=list
    )

    @property
    def input_tokens(self) -> int:
        return sum(
            call.input_tokens
            for call in self.llm_calls
        )

    @property
    def output_tokens(self) -> int:
        return sum(
            call.output_tokens
            for call in self.llm_calls
        )

    @property
    def thinking_tokens(self) -> int:
        return sum(
            call.thinking_tokens
            for call in self.llm_calls
        )

    @property
    def total_tokens(self) -> int:
        return sum(
            call.total_tokens
            for call in self.llm_calls
        )

    @property
    def estimated_cost_usd(
        self,
    ) -> float:
        return sum(
            call.estimated_cost_usd
            for call in self.llm_calls
        )


_current_telemetry: ContextVar[
    RequestTelemetry | None
] = ContextVar(
    "current_monitoring_telemetry",
    default=None,
)


@contextmanager
def monitoring_context(
    response_id: str,
) -> Iterator[RequestTelemetry]:
    """
    Attach an LLM telemetry collector to the current
    request execution context.
    """

    telemetry = RequestTelemetry(
        response_id=response_id
    )

    token = (
        _current_telemetry.set(
            telemetry
        )
    )

    try:
        yield telemetry

    finally:
        _current_telemetry.reset(
            token
        )


def record_gemini_response(
    *,
    response: Any,
    model: str,
    purpose: str,
) -> None:
    """
    Record token usage from a Gemini GenerateContentResponse.
    """

    telemetry = (
        _current_telemetry.get()
    )

    if telemetry is None:
        return

    usage = getattr(
        response,
        "usage_metadata",
        None,
    )

    if usage is None:
        return

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

    telemetry.llm_calls.append(
        LLMCall(
            purpose=purpose,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
        )
    )
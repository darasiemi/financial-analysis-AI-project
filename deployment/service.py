from __future__ import annotations

import time
from typing import Any

from agent.gemini import GeminiFinancialAgent
from agent.pipeline import run_agent
from rag.gemini import GeminiGenerator
from rag.pipeline import run_rag


DEFAULT_MODEL = "gemini-2.5-flash"


def run_rag_query(
    question: str,
    *,
    retrieval_mode: str = "hybrid",
    top_k: int = 8,
    ticker: str | None = None,
    report_year: int | None = None,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """
    Execute the standard RAG pipeline and normalize the result
    for the Streamlit application.
    """

    generator = GeminiGenerator(
        model=model
    )

    start = time.perf_counter()

    result = run_rag(
        question,
        generator=generator,
        mode=retrieval_mode,
        top_k=top_k,
        ticker=ticker,
        report_year=report_year,
    )

    elapsed = time.perf_counter() - start

    return {
        "pipeline": "rag",
        "answer": result.get(
            "answer",
            "No answer was generated.",
        ),
        "results": result.get(
            "results",
            [],
        ),
        "context": result.get(
            "context",
            "",
        ),
        "tool_calls": [],
        "timing": {
            "total_seconds": elapsed,
        },
    }


def _extract_agent_answer(
    result: dict[str, Any],
) -> str:
    """
    Normalize agent answer formats.

    This supports both a plain-string answer and an agent result
    containing an answer field.
    """

    answer = result.get("answer")

    if isinstance(answer, str):
        return answer

    if isinstance(answer, dict):
        for key in (
            "answer",
            "final_answer",
            "text",
        ):
            value = answer.get(key)

            if isinstance(value, str):
                return value

    agent_result = result.get(
        "agent_result"
    )

    if isinstance(agent_result, dict):
        for key in (
            "answer",
            "final_answer",
            "text",
        ):
            value = agent_result.get(key)

            if isinstance(value, str):
                return value

    return str(answer or "")


def _extract_tool_calls(
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Extract tool traces without coupling the UI to one exact
    internal representation.
    """

    candidates = [
        result.get("tool_calls"),
        result.get("tools_used"),
    ]

    agent_result = result.get(
        "agent_result"
    )

    if isinstance(agent_result, dict):
        candidates.extend(
            [
                agent_result.get(
                    "tool_calls"
                ),
                agent_result.get(
                    "tools_used"
                ),
            ]
        )

    answer = result.get("answer")

    if isinstance(answer, dict):
        candidates.extend(
            [
                answer.get("tool_calls"),
                answer.get("tools_used"),
            ]
        )

    for candidate in candidates:
        if isinstance(candidate, list):
            return candidate

    return []


def _extract_initial_results(
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    retrieval = result.get(
        "initial_retrieval"
    )

    if isinstance(retrieval, list):
        return retrieval

    if isinstance(retrieval, dict):
        for key in (
            "results",
            "documents",
            "items",
        ):
            value = retrieval.get(key)

            if isinstance(value, list):
                return value

    return []


def run_agent_query(
    question: str,
    *,
    top_k: int = 8,
    ticker: str | None = None,
    report_year: int | None = None,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """
    Execute the agentic financial-analysis pipeline.
    """

    agent = GeminiFinancialAgent(
        model=model
    )

    result = run_agent(
        question,
        agent=agent,
        ticker=ticker,
        report_year=report_year,
        top_k=top_k,
    )

    return {
        "pipeline": "agent",
        "answer": _extract_agent_answer(
            result
        ),
        "results": _extract_initial_results(
            result
        ),
        "context": result.get(
            "initial_context",
            "",
        ),
        "tool_calls": _extract_tool_calls(
            result
        ),
        "timing": result.get(
            "timing",
            {},
        ),
        "raw_result": result,
    }


def run_query(
    question: str,
    *,
    pipeline: str,
    retrieval_mode: str = "hybrid",
    top_k: int = 8,
    ticker: str | None = None,
    report_year: int | None = None,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """
    Unified application-facing interface.
    """

    if pipeline == "rag":
        return run_rag_query(
            question,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
            ticker=ticker,
            report_year=report_year,
            model=model,
        )

    if pipeline == "agent":
        return run_agent_query(
            question,
            top_k=top_k,
            ticker=ticker,
            report_year=report_year,
            model=model,
        )

    raise ValueError(
        f"Unsupported pipeline: {pipeline}"
    )
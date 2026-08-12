from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from agent.gemini import (
    GeminiFinancialAgent,
)
from agent.pipeline import (
    run_agent,
)
from rag.gemini import (
    GeminiGenerator,
)
from rag.pipeline import (
    run_rag,
)


DEFAULT_MODEL = (
    "gemini-2.5-flash"
)

POWERPOINT_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "presentationml.presentation"
)


# =============================================================
# RAG
# =============================================================


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
    Execute the standard RAG pipeline and
    normalize its output for the API.
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

    elapsed = (
        time.perf_counter()
        - start
    )

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

        "generated_files": [],

        "timing": {
            "total_seconds": elapsed,
        },

        "raw_result": result,
    }


# =============================================================
# Agent result extraction
# =============================================================


def _extract_agent_answer(
    result: dict[str, Any],
) -> str:
    """
    Normalize different agent answer structures.
    """

    answer = result.get(
        "answer"
    )

    if isinstance(
        answer,
        str,
    ):
        return answer

    if isinstance(
        answer,
        dict,
    ):
        for key in (
            "answer",
            "final_answer",
            "text",
        ):
            value = answer.get(
                key
            )

            if isinstance(
                value,
                str,
            ):
                return value

    agent_result = result.get(
        "agent_result"
    )

    if isinstance(
        agent_result,
        dict,
    ):
        for key in (
            "answer",
            "final_answer",
            "text",
        ):
            value = (
                agent_result.get(
                    key
                )
            )

            if isinstance(
                value,
                str,
            ):
                return value

    return str(
        answer
        or ""
    )


def _extract_tool_calls(
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Extract tool traces from the different
    result structures supported by the agent.
    """

    candidates = [
        result.get(
            "tool_calls"
        ),
        result.get(
            "tools_used"
        ),
    ]

    agent_result = result.get(
        "agent_result"
    )

    if isinstance(
        agent_result,
        dict,
    ):
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

    answer = result.get(
        "answer"
    )

    if isinstance(
        answer,
        dict,
    ):
        candidates.extend(
            [
                answer.get(
                    "tool_calls"
                ),
                answer.get(
                    "tools_used"
                ),
            ]
        )

    for candidate in candidates:
        if isinstance(
            candidate,
            list,
        ):
            return candidate

    return []


def _extract_initial_results(
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Extract initial retrieval evidence.
    """

    retrieval = result.get(
        "initial_retrieval"
    )

    if isinstance(
        retrieval,
        list,
    ):
        return retrieval

    if isinstance(
        retrieval,
        dict,
    ):
        for key in (
            "results",
            "documents",
            "items",
        ):
            value = (
                retrieval.get(
                    key
                )
            )

            if isinstance(
                value,
                list,
            ):
                return value

    return []


# =============================================================
# Generated file extraction
# =============================================================


def _unwrap_tool_response(
    response: Any,
) -> Any:
    """
    Unwrap common nested tool-response formats.
    """

    if not isinstance(
        response,
        dict,
    ):
        return response

    # Some tool runners wrap the actual response.
    for key in (
        "result",
        "output",
    ):
        nested = response.get(
            key
        )

        if isinstance(
            nested,
            dict,
        ):
            return nested

    return response


def _extract_generated_files(
    tool_calls: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    """
    Extract downloadable files produced by
    agent tools.

    Currently supports PowerPoint generation.
    """

    generated_files: list[
        dict[str, Any]
    ] = []

    seen: set[str] = set()

    for call in tool_calls:

        tool_name = str(
            call.get(
                "tool",
                call.get(
                    "name",
                    call.get(
                        "tool_name",
                        "",
                    ),
                ),
            )
        )

        if tool_name != (
            "create_powerpoint"
        ):
            continue

        response = call.get(
            "response",
            call.get(
                "result",
                call.get(
                    "raw_response"
                ),
            ),
        )

        response = (
            _unwrap_tool_response(
                response
            )
        )

        if not isinstance(
            response,
            dict,
        ):
            continue

        if (
            response.get(
                "success"
            )
            is not True
        ):
            continue

        filename = response.get(
            "filename"
        )

        # Backwards compatibility with
        # older presentation tool output.
        if not filename:

            path = response.get(
                "path"
            )

            if path:
                filename = (
                    Path(
                        str(path)
                    )
                    .name
                )

        if not filename:
            continue

        filename = str(
            filename
        )

        if filename in seen:
            continue

        seen.add(
            filename
        )

        generated_files.append(
            {
                "filename": (
                    filename
                ),

                "file_type": (
                    response.get(
                        "file_type",
                        "powerpoint",
                    )
                ),

                "format": (
                    response.get(
                        "format",
                        "pptx",
                    )
                ),

                "mime_type": (
                    response.get(
                        "mime_type",
                        POWERPOINT_MIME_TYPE,
                    )
                ),

                "size_bytes": (
                    response.get(
                        "size_bytes"
                    )
                ),
            }
        )

    return generated_files


# =============================================================
# Agent
# =============================================================


def run_agent_query(
    question: str,
    *,
    top_k: int = 8,
    ticker: str | None = None,
    report_year: int | None = None,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """
    Execute the agentic financial-analysis
    pipeline.
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

    tool_calls = (
        _extract_tool_calls(
            result
        )
    )

    generated_files = (
        _extract_generated_files(
            tool_calls
        )
    )

    return {
        "pipeline": "agent",

        "answer": (
            _extract_agent_answer(
                result
            )
        ),

        "results": (
            _extract_initial_results(
                result
            )
        ),

        "context": result.get(
            "initial_context",
            "",
        ),

        "tool_calls": (
            tool_calls
        ),

        "generated_files": (
            generated_files
        ),

        "timing": result.get(
            "timing",
            {},
        ),

        "raw_result": result,
    }


# =============================================================
# Unified interface
# =============================================================


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
            retrieval_mode=(
                retrieval_mode
            ),
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
        f"Unsupported pipeline: "
        f"{pipeline}"
    )
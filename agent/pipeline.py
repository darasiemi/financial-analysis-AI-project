from __future__ import annotations

import time
from typing import Any, Protocol

from agent.context import (
    build_initial_context,
)
from agent.tools.retrieval import (
    search_hybrid,
)


class FinancialAgent(Protocol):
    """
    Interface required by the orchestration pipeline.

    This keeps the pipeline independent of Gemini.
    """

    def ask(
        self,
        *,
        question: str,
        initial_context: str,
    ) -> dict[str, Any]: ...


def initial_retrieval(
    question: str,
    *,
    ticker: str | None = None,
    report_year: int | None = None,
    top_k: int = 8,
) -> dict[str, Any]:
    """
    Perform first-stage hybrid retrieval over the annual-report
    corpus.

    No query rewriting currently occurs here.

    The exact user question is used as the retrieval query.
    """

    return search_hybrid(
        query=question,
        ticker=ticker,
        report_year=report_year,
        top_k=top_k,
    )


def run_agent(
    question: str,
    *,
    agent: FinancialAgent,
    ticker: str | None = None,
    report_year: int | None = None,
    top_k: int = 8,
) -> dict[str, Any]:
    """
    Run the two-stage financial-analysis agent.

    Stage 1:
        Perform initial hybrid retrieval over local annual reports.

    Stage 2:
        Pass that evidence to the agent. Gemini may then invoke
        additional retrieval, table, calculator, or web tools.

    Returns:
        Complete observable execution information.
    """

    total_start = time.perf_counter()

    # =========================================================
    # Stage 1: initial local retrieval
    # =========================================================

    initial_retrieval_query = question

    retrieval_start = time.perf_counter()

    retrieval_result = initial_retrieval(
        initial_retrieval_query,
        ticker=ticker,
        report_year=report_year,
        top_k=top_k,
    )

    retrieval_seconds = time.perf_counter() - retrieval_start

    initial_context = build_initial_context(retrieval_result)

    # =========================================================
    # Stage 2: Gemini + additional tools
    # =========================================================

    agent_start = time.perf_counter()

    agent_result = agent.ask(
        question=question,
        initial_context=(initial_context),
    )

    agent_seconds = time.perf_counter() - agent_start

    total_seconds = time.perf_counter() - total_start

    return {
        "question": question,
        # Currently identical to the user question because
        # Stage 1 performs no rewriting.
        "initial_retrieval_query": (initial_retrieval_query),
        "ticker": ticker,
        "report_year": (report_year),
        "initial_retrieval": (retrieval_result),
        "initial_context": (initial_context),
        # Only additional calls selected by Gemini.
        "tool_calls": (
            agent_result.get(
                "tool_calls",
                [],
            )
        ),
        "answer": (agent_result["answer"]),
        "timing": {
            "initial_retrieval_seconds": (retrieval_seconds),
            "agent_seconds": (agent_seconds),
            "total_seconds": (total_seconds),
        },
    }

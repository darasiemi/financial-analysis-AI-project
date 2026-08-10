import os

from agent.gemini import (
    GeminiFinancialAgent,
)
from agent.pipeline import (
    run_agent,
)
from evaluation.schemas import (
    EvalExample,
    PipelineResult,
)


def _unwrap_response(
    response,
):
    if (
        isinstance(response, dict)
        and "result" in response
        and isinstance(
            response["result"],
            dict,
        )
    ):
        return response[
            "result"
        ]

    return response


class AgentAdapter:

    def __init__(
        self,
        *,
        top_k: int = 8,
        model: str | None = None,
        max_tool_calls: int = 12,
    ) -> None:

        self.top_k = top_k

        self.agent = (
            GeminiFinancialAgent(
                model=(
                    model
                    or os.environ.get(
                        "GEMINI_AGENT_MODEL",
                        "gemini-2.5-flash",
                    )
                ),
                max_tool_calls=(
                    max_tool_calls
                ),
            )
        )

    def run(
        self,
        example: EvalExample,
    ) -> PipelineResult:

        result = run_agent(
            example.question,
            agent=self.agent,
            ticker=example.ticker,
            report_year=(
                example.report_year
            ),
            top_k=self.top_k,
        )

        initial_documents = (
            result[
                "initial_retrieval"
            ].get(
                "documents",
                [],
            )
        )

        initial_ids = [
            document["source_id"]
            for document
            in initial_documents
        ]

        all_ids = list(
            initial_ids
        )

        contexts = [
            document["text"]
            for document
            in initial_documents
        ]

        # Add evidence gathered through later tool calls.
        for call in result.get(
            "tool_calls",
            [],
        ):

            response = (
                _unwrap_response(
                    call.get(
                        "response"
                    )
                )
            )

            if not isinstance(
                response,
                dict,
            ):
                continue

            documents = response.get(
                "documents",
                [],
            )

            for document in documents:

                source_id = (
                    document.get(
                        "source_id"
                    )
                )

                text = document.get(
                    "text"
                )

                if (
                    source_id
                    and source_id
                    not in all_ids
                ):
                    all_ids.append(
                        source_id
                    )

                if (
                    text
                    and text
                    not in contexts
                ):
                    contexts.append(
                        text
                    )

        return PipelineResult(
            answer=result["answer"],
            initial_retrieved_source_ids=(
                initial_ids
            ),
            retrieved_source_ids=(
                all_ids
            ),
            contexts=contexts,
            latency_seconds=(
                result[
                    "timing"
                ][
                    "total_seconds"
                ]
            ),
            tool_calls=result.get(
                "tool_calls",
                [],
            ),
            metadata={
                "pipeline": "agent",
            },
        )
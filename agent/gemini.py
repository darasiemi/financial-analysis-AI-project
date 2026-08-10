import os
from typing import Any

from google import genai
from google.genai import types

from agent.tools import (
    calculate,
    create_powerpoint,
    get_table,
    search_hybrid,
    search_keyword,
    search_semantic,
    web_search,
)


SYSTEM_INSTRUCTION = """
You are a financial-analysis research agent.

You answer financial and company questions using:

1. Annual reports stored in the local financial-report database.
2. Structured tables extracted from those reports.
3. Deterministic calculations.
4. Public web information when necessary.
5. PowerPoint presentation generation when explicitly requested.

You normally receive INITIAL EVIDENCE retrieved from the
annual-report database before you begin.

INITIAL EVIDENCE

Inspect the supplied initial annual-report evidence first.

If the evidence is sufficient to answer the question reliably,
answer from it.

If the evidence is incomplete, ambiguous, or insufficient, use
the available tools to gather additional evidence.

LOCAL SEARCH TOOLS

search_keyword:
Use for exact names, executive titles, accounting terminology,
financial metrics, and exact phrases.

search_semantic:
Use when the user's wording may differ from terminology used in
the reports.

search_hybrid:
Use for general-purpose retrieval or when refining the initial
search.

You may search multiple times when needed.

If a question asks about multiple reporting periods, search the
periods separately when this improves retrieval.

STRUCTURED TABLES

Search results with content_type="table" have a source_id.

When exact financial values, rows, columns, periods, or
relationships matter, call get_table using that source_id.

Do not rely only on a textual table representation when the exact
table structure is important.

CALCULATIONS

Use calculate for arithmetic such as:

- percentage change
- absolute change
- ratios
- margins
- averages

Do not approximate important financial calculations in natural
language when the calculator tool can compute them exactly.

WEB SEARCH

Use web_search when:

- the user asks for current or latest information;
- the requested information is newer than available annual reports;
- external verification is explicitly requested;
- the local reports do not contain enough evidence;
- public information outside the annual reports is needed.

Do not use web search merely because it is available.

For facts contained in annual reports, prefer the local database
because it is the primary evidence source for this system.

POWERPOINT CREATION

Use create_powerpoint only when the user explicitly asks for:

- a PowerPoint presentation;
- slides;
- a slide deck;
- a presentation;
- a financial-analysis presentation.

Before calling create_powerpoint:

- gather the required evidence;
- inspect structured tables when exact financial values matter;
- use calculate for arithmetic;
- use web_search only when current or external information is
  required.

Build concise, executive-style slides rather than copying raw
retrieved context into the presentation.

Prefer visual slide types such as:

- metrics
- comparison
- highlight
- chart

Use bullets only when appropriate.

A typical financial presentation may include:

1. Executive summary
2. Key financial metrics
3. Performance comparison
4. Important drivers or observations
5. Conclusion
6. Sources

Do not invent missing information.

Preserve original currencies, units, reporting periods, and
company/group distinctions.

Include source references in slide content where appropriate.

After create_powerpoint succeeds, provide a short confirmation
stating where the PowerPoint was saved.

TOOL FAILURES

If a tool returns success=false:

- inspect the returned error;
- try an alternative retrieval tool or refined query if useful;
- do not assume information does not exist merely because one
  tool failed.

SOURCE HANDLING

Clearly distinguish:

- annual-report evidence;
- structured table evidence;
- public web evidence.

For annual-report evidence, mention the company, report year, and
PDF page when available.

For web evidence, identify the returned source when relevant.

FINANCIAL ACCURACY

Always:

- preserve currencies;
- preserve units;
- distinguish thousands, millions, and billions;
- preserve reporting periods;
- distinguish Group and Company figures;
- distinguish percentages from absolute values.

Never invent company-specific facts.

If evidence conflicts, explain the conflict.

If evidence remains insufficient after reasonable tool use, say so
clearly.

Keep the final response focused and evidence-based.
""".strip()


class GeminiFinancialAgent:
    """
    Gemini implementation of the financial-analysis agent.

    Gemini receives initial retrieval evidence from the pipeline
    and may automatically invoke additional tools.

    The returned result contains:
    - final answer;
    - tools called by Gemini;
    - arguments generated for each call;
    - corresponding function responses.
    """

    def __init__(
        self,
        *,
        model: str = "gemini-2.5-flash",
        max_tool_calls: int = 12,
    ) -> None:

        api_key = os.environ.get(
            "GEMINI_API_KEY"
        )

        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured."
            )

        self.model = model

        self.client = genai.Client(
            api_key=api_key
        )

        self.config = (
            types.GenerateContentConfig(
                system_instruction=(
                    SYSTEM_INSTRUCTION
                ),
                tools=[
                    search_keyword,
                    search_semantic,
                    search_hybrid,
                    get_table,
                    calculate,
                    web_search,
                    create_powerpoint,
                ],
                automatic_function_calling=(
                    types.AutomaticFunctionCallingConfig(
                        maximum_remote_calls=(
                            max_tool_calls + 1
                        ),
                        ignore_call_history=False,
                    )
                ),
                temperature=0.1,
            )
        )

    @staticmethod
    def _normalise_value(
        value: Any,
    ) -> Any:
        """
        Convert Gemini/Pydantic values into ordinary Python
        structures suitable for printing and inspection.
        """

        if value is None:
            return None

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ):
            return value

        if isinstance(
            value,
            dict,
        ):
            return {
                str(key): (
                    GeminiFinancialAgent
                    ._normalise_value(item)
                )
                for key, item in value.items()
            }

        if isinstance(
            value,
            (
                list,
                tuple,
            ),
        ):
            return [
                GeminiFinancialAgent
                ._normalise_value(item)
                for item in value
            ]

        if hasattr(
            value,
            "model_dump",
        ):
            try:
                return (
                    GeminiFinancialAgent
                    ._normalise_value(
                        value.model_dump()
                    )
                )
            except Exception:
                pass

        return str(value)

    @staticmethod
    def _unwrap_tool_response(
        response: Any,
    ) -> Any:
        """
        Unwrap automatic function-calling responses.

        Gemini may wrap the Python function result like:

            {
                "result": {
                    ...
                }
            }
        """

        if not isinstance(
            response,
            dict,
        ):
            return response

        if (
            "result" in response
            and isinstance(
                response["result"],
                dict,
            )
        ):
            return response[
                "result"
            ]

        return response

    @classmethod
    def _extract_tool_trace(
        cls,
        response: Any,
    ) -> list[dict[str, Any]]:
        """
        Extract automatic function calls and corresponding
        responses from Gemini's function-calling history.

        This exposes tool activity without exposing private
        model reasoning.
        """

        history = getattr(
            response,
            "automatic_function_calling_history",
            None,
        )

        if not history:
            return []

        trace: list[
            dict[str, Any]
        ] = []

        unresolved_calls: list[
            dict[str, Any]
        ] = []

        call_number = 0

        for content in history:

            parts = getattr(
                content,
                "parts",
                None,
            )

            if not parts:
                continue

            for part in parts:

                # =================================================
                # Function call
                # =================================================

                function_call = getattr(
                    part,
                    "function_call",
                    None,
                )

                if function_call is not None:

                    call_number += 1

                    arguments = getattr(
                        function_call,
                        "args",
                        None,
                    )

                    arguments = (
                        cls._normalise_value(
                            arguments
                        )
                        or {}
                    )

                    call_id = getattr(
                        function_call,
                        "id",
                        None,
                    )

                    entry = {
                        "call_number": (
                            call_number
                        ),
                        "call_id": (
                            call_id
                        ),
                        "tool": getattr(
                            function_call,
                            "name",
                            None,
                        ),
                        "arguments": (
                            arguments
                        ),
                        "response": None,
                    }

                    trace.append(
                        entry
                    )

                    unresolved_calls.append(
                        entry
                    )

                    continue

                # =================================================
                # Function response
                # =================================================

                function_response = getattr(
                    part,
                    "function_response",
                    None,
                )

                if function_response is None:
                    continue

                response_name = getattr(
                    function_response,
                    "name",
                    None,
                )

                response_data = getattr(
                    function_response,
                    "response",
                    None,
                )

                response_data = (
                    cls._normalise_value(
                        response_data
                    )
                )

                response_id = getattr(
                    function_response,
                    "id",
                    None,
                )

                matched_entry = None

                # Prefer matching by call ID.
                if response_id is not None:

                    for entry in unresolved_calls:

                        if (
                            entry["call_id"]
                            == response_id
                            and entry[
                                "response"
                            ]
                            is None
                        ):
                            matched_entry = (
                                entry
                            )
                            break

                # Fallback: match by tool name.
                if matched_entry is None:

                    for entry in unresolved_calls:

                        if (
                            entry["tool"]
                            == response_name
                            and entry[
                                "response"
                            ]
                            is None
                        ):
                            matched_entry = (
                                entry
                            )
                            break

                if matched_entry is not None:

                    matched_entry[
                        "response"
                    ] = response_data

        return trace

    @classmethod
    def _find_successful_powerpoint(
        cls,
        tool_trace: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """
        Find a successful create_powerpoint call in the tool trace.
        """

        for call in tool_trace:

            if (
                call.get("tool")
                != "create_powerpoint"
            ):
                continue

            response = (
                cls._unwrap_tool_response(
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

            if (
                response.get(
                    "success"
                )
                is True
            ):
                return response

        return None

    @classmethod
    def _find_successful_tools(
        cls,
        tool_trace: list[dict[str, Any]],
    ) -> list[str]:
        """
        Return the names of successfully executed tools.
        """

        successful_tools = []

        for call in tool_trace:

            response = (
                cls._unwrap_tool_response(
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

            if (
                response.get(
                    "success"
                )
                is True
            ):
                tool_name = call.get(
                    "tool"
                )

                if tool_name:
                    successful_tools.append(
                        str(tool_name)
                    )

        return successful_tools

    def ask(
        self,
        *,
        question: str,
        initial_context: str,
    ) -> dict[str, Any]:
        """
        Answer a financial-analysis question.

        Gemini first receives initial evidence from the local
        annual-report retrieval pipeline.

        It may then invoke additional tools automatically.

        If Gemini successfully performs an action such as creating
        a PowerPoint but returns no final prose, this method
        constructs a deterministic fallback response.

        Returns:
            {
                "answer": str,
                "tool_calls": list
            }
        """

        prompt = f"""
USER QUESTION
=============
{question}


INITIAL ANNUAL-REPORT EVIDENCE
==============================
{initial_context}


TASK
====
Answer the user's question.

First inspect the initial evidence.

If it is sufficient, answer from it.

If it is insufficient, use the available tools to retrieve,
inspect, calculate, verify, or generate the requested output.

If the user explicitly asks for a presentation, PowerPoint,
slides, or slide deck:

1. Gather the required evidence first.
2. Perform any required calculations.
3. Construct concise slide content.
4. Prefer metrics, comparison, highlight, and chart slides where
   appropriate.
5. Call create_powerpoint only after the analysis is complete.
6. After create_powerpoint succeeds, provide a short confirmation
   stating where the PowerPoint was saved.
""".strip()

        response = (
            self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=self.config,
            )
        )

        # =====================================================
        # Extract tool history first
        # =====================================================

        tool_trace = (
            self._extract_tool_trace(
                response
            )
        )

        # =====================================================
        # Normal case: Gemini returned final text
        # =====================================================

        if response.text:

            return {
                "answer": (
                    response.text
                ),
                "tool_calls": (
                    tool_trace
                ),
            }

        # =====================================================
        # No final text:
        # check whether PowerPoint creation succeeded
        # =====================================================

        successful_powerpoint = (
            self._find_successful_powerpoint(
                tool_trace
            )
        )

        if successful_powerpoint:

            output_path = (
                successful_powerpoint.get(
                    "path",
                    "outputs/",
                )
            )

            slides_created = (
                successful_powerpoint.get(
                    "slides_created"
                )
            )

            title = (
                successful_powerpoint.get(
                    "title"
                )
            )

            answer_parts = [
                "PowerPoint presentation "
                "created successfully."
            ]

            if title:
                answer_parts.append(
                    f"Title: {title}."
                )

            if slides_created is not None:
                answer_parts.append(
                    "Slides created: "
                    f"{slides_created}."
                )

            answer_parts.append(
                f"Saved to: {output_path}"
            )

            return {
                "answer": " ".join(
                    answer_parts
                ),
                "tool_calls": (
                    tool_trace
                ),
            }

        # =====================================================
        # Other tools succeeded but no final text
        # =====================================================

        successful_tools = (
            self._find_successful_tools(
                tool_trace
            )
        )

        if successful_tools:

            return {
                "answer": (
                    "The agent completed tool execution, "
                    "but Gemini returned no final text response. "
                    "Successful tools: "
                    + ", ".join(
                        successful_tools
                    )
                ),
                "tool_calls": (
                    tool_trace
                ),
            }

        # =====================================================
        # Nothing useful completed
        # =====================================================

        finish_reason = None

        candidates = getattr(
            response,
            "candidates",
            None,
        )

        if candidates:

            finish_reason = getattr(
                candidates[0],
                "finish_reason",
                None,
            )

        raise RuntimeError(
            "Gemini returned no final text response "
            "and no successful tool execution was detected. "
            f"Finish reason: {finish_reason}"
        )
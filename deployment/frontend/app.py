from __future__ import annotations

import json
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from deployment.backend.database import (
    get_available_filters,
    get_corpus_stats,
)
from deployment.backend.service import run_query
from ingestion.processing.database import (
    load_environment,
)


# =============================================================
# Application configuration
# =============================================================

load_environment()

st.set_page_config(
    page_title="Financial Analysis AI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================
# Styling
# =============================================================

st.markdown(
    """
    <style>
        .block-container {
            max-width: 1450px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        .hero {
            padding: 2.2rem 2.4rem;
            border-radius: 22px;
            background:
                linear-gradient(
                    135deg,
                    #0f172a 0%,
                    #172554 52%,
                    #0f766e 100%
                );
            color: white;
            margin-bottom: 1.7rem;
            box-shadow:
                0 14px 40px rgba(15, 23, 42, 0.18);
        }

        .hero h1 {
            font-size: 2.35rem;
            font-weight: 750;
            margin-bottom: 0.4rem;
        }

        .hero p {
            font-size: 1.05rem;
            color: #dbeafe;
            margin-bottom: 0;
            max-width: 900px;
        }

        .answer-box {
            padding: 1.5rem 1.6rem;
            border-radius: 18px;
            border: 1px solid rgba(148, 163, 184, 0.25);
            background: rgba(248, 250, 252, 0.55);
            margin-top: 0.5rem;
            margin-bottom: 1rem;
        }

        .source-card {
            border: 1px solid rgba(148, 163, 184, 0.25);
            border-radius: 14px;
            padding: 1rem 1.1rem;
            margin-bottom: 0.75rem;
        }

        .source-meta {
            font-size: 0.84rem;
            opacity: 0.72;
            margin-bottom: 0.4rem;
        }

        .tool-card {
            padding: 0.8rem 1rem;
            border-left: 4px solid #0f766e;
            background: rgba(15, 118, 110, 0.06);
            border-radius: 8px;
            margin-bottom: 0.6rem;
        }

        div[data-testid="stMetric"] {
            border: 1px solid rgba(148, 163, 184, 0.2);
            padding: 0.9rem;
            border-radius: 14px;
            background: rgba(248, 250, 252, 0.35);
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================
# Helpers
# =============================================================

@st.cache_data(ttl=300)
def load_filters() -> dict[str, list[Any]]:
    return get_available_filters()


@st.cache_data(ttl=300)
def load_stats() -> dict[str, int]:
    return get_corpus_stats()


def display_source(
    result: dict[str, Any],
    rank: int,
) -> None:
    ticker = result.get(
        "ticker",
        "Unknown",
    )

    year = result.get(
        "report_year",
        "—",
    )

    content_type = result.get(
        "content_type",
        "document",
    )

    page_start = result.get(
        "page_start",
        result.get(
            "pdf_page_start"
        ),
    )

    page_end = result.get(
        "page_end",
        result.get(
            "pdf_page_end"
        ),
    )

    section = result.get(
        "section_title"
    )

    text = result.get(
        "text",
        "",
    )

    source_id = result.get(
        "source_id",
        result.get(
            "document_id",
            "",
        ),
    )

    if (
        page_start is not None
        and page_end is not None
    ):
        pages = (
            str(page_start)
            if page_start == page_end
            else f"{page_start}–{page_end}"
        )
    else:
        pages = "—"

    with st.expander(
        (
            f"#{rank} · {ticker} {year} · "
            f"{content_type.title()} · Page {pages}"
        ),
        expanded=rank <= 2,
    ):
        if section:
            st.markdown(
                f"**Section:** {section}"
            )

        if source_id:
            st.caption(
                f"Source ID: {source_id}"
            )

        st.write(text)


def _tool_name(
    call: dict[str, Any],
) -> str:
    return str(
        call.get(
            "tool",
            call.get(
                "name",
                "Unknown tool",
            ),
        )
    )


def _tool_arguments(
    call: dict[str, Any],
) -> Any:
    return call.get(
        "arguments",
        call.get(
            "args",
            {},
        ),
    )


def _tool_status(
    call: dict[str, Any],
) -> str:
    if call.get("error"):
        return "Failed"

    status = call.get("status")

    if status:
        return str(status)

    success = call.get("success")

    if success is False:
        return "Failed"

    if success is True:
        return "Success"

    return "Completed"


def display_tool_trace(
    tool_calls: list[dict[str, Any]],
) -> None:
    if not tool_calls:
        st.info(
            "The agent did not invoke any additional tools."
        )
        return

    for index, call in enumerate(
        tool_calls,
        start=1,
    ):
        name = _tool_name(call)
        status = _tool_status(call)

        with st.expander(
            f"Tool {index}: {name} · {status}",
            expanded=index == 1,
        ):
            st.markdown("**Arguments**")
            st.json(
                _tool_arguments(call)
            )

            response = call.get(
                "response",
                call.get(
                    "result",
                    call.get(
                        "raw_response"
                    ),
                ),
            )

            if response is not None:
                st.markdown(
                    "**Tool response**"
                )

                if isinstance(
                    response,
                    (dict, list),
                ):
                    st.json(response)
                else:
                    st.code(
                        str(response),
                        language="text",
                    )

            error = call.get("error")

            if error:
                st.error(str(error))


def retrieval_dataframe(
    results: list[dict[str, Any]],
) -> pd.DataFrame:
    rows = []

    for index, result in enumerate(
        results,
        start=1,
    ):
        score = result.get(
            "rrf_score"
        )

        if score is None:
            score = result.get(
                "similarity"
            )

        if score is None:
            score = result.get(
                "score"
            )

        rows.append(
            {
                "Rank": index,
                "Ticker": result.get(
                    "ticker"
                ),
                "Year": result.get(
                    "report_year"
                ),
                "Type": result.get(
                    "content_type"
                ),
                "Section": result.get(
                    "section_title"
                ),
                "Score": score,
                "Keyword Rank": result.get(
                    "keyword_rank"
                ),
                "Vector Rank": result.get(
                    "vector_rank"
                ),
            }
        )

    return pd.DataFrame(rows)


# =============================================================
# Header
# =============================================================

st.markdown(
    """
    <div class="hero">
        <h1>Financial Analysis AI</h1>
        <p>
            Ask analytical questions across corporate annual reports.
            Compare reported metrics, inspect retrieved evidence,
            reason over structured financial tables, and use an
            agentic workflow when additional tools are required.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =============================================================
# Sidebar
# =============================================================

try:
    filters = load_filters()
    stats = load_stats()

except Exception as exc:
    filters = {
        "tickers": [],
        "years": [],
    }

    stats = {
        "documents": 0,
        "companies": 0,
        "years": 0,
        "tables": 0,
        "narratives": 0,
    }

    st.sidebar.warning(
        "Database metadata could not be loaded."
    )

    st.sidebar.caption(str(exc))


with st.sidebar:
    st.header("Analysis settings")

    pipeline_label = st.radio(
        "Pipeline",
        options=[
            "Agent",
            "RAG",
        ],
        horizontal=True,
    )

    pipeline = pipeline_label.lower()

    if pipeline == "rag":
        retrieval_mode = st.selectbox(
            "Retrieval strategy",
            options=[
                "hybrid",
                "keyword",
                "vector",
            ],
            index=0,
        )
    else:
        retrieval_mode = "hybrid"

    ticker_options = [
        "All companies",
        *filters["tickers"],
    ]

    selected_ticker = st.selectbox(
        "Company",
        ticker_options,
    )

    ticker = (
        None
        if selected_ticker == "All companies"
        else selected_ticker
    )

    year_options = [
        "All years",
        *filters["years"],
    ]

    selected_year = st.selectbox(
        "Report year",
        year_options,
    )

    report_year = (
        None
        if selected_year == "All years"
        else int(selected_year)
    )

    top_k = st.slider(
        "Top-K evidence",
        min_value=3,
        max_value=15,
        value=8,
        step=1,
    )

    model = st.selectbox(
        "Gemini model",
        [
            "gemini-2.5-flash",
        ],
    )

    st.divider()

    st.caption(
        "Annual reports are the primary source. "
        "The agent may use additional tools when necessary."
    )


# =============================================================
# Corpus overview
# =============================================================

metric_columns = st.columns(5)

metric_columns[0].metric(
    "Indexed documents",
    f"{stats['documents']:,}",
)

metric_columns[1].metric(
    "Companies",
    stats["companies"],
)

metric_columns[2].metric(
    "Report years",
    stats["years"],
)

metric_columns[3].metric(
    "Narrative",
    f"{stats['narratives']:,}",
)

metric_columns[4].metric(
    "Tables",
    f"{stats['tables']:,}",
)


# =============================================================
# Question form
# =============================================================

st.subheader("Ask a financial question")

examples = [
    (
        "Compare GTCO's profit before tax in 2023 "
        "and 2024 and calculate the percentage increase."
    ),
    (
        "How did Zenith Bank's gross loans change "
        "from 2023 to 2024?"
    ),
    (
        "Compare MTN Nigeria's profitability across "
        "the available reporting periods."
    ),
]

example = st.selectbox(
    "Example questions",
    ["Write my own question", *examples],
)

default_question = (
    ""
    if example == "Write my own question"
    else example
)

with st.form(
    "analysis_form",
    clear_on_submit=False,
):
    question = st.text_area(
        "Question",
        value=default_question,
        height=110,
        placeholder=(
            "e.g. Compare GTCO's profit before tax "
            "in 2023 and 2024 and calculate the "
            "percentage increase."
        ),
    )

    submitted = st.form_submit_button(
        "Run financial analysis",
        type="primary",
        use_container_width=True,
    )


# =============================================================
# Execute
# =============================================================

if submitted:
    if not question.strip():
        st.warning(
            "Enter a financial-analysis question."
        )
        st.stop()

    with st.status(
        "Analysing annual reports...",
        expanded=True,
    ) as status:
        st.write(
            "Searching the financial-report corpus..."
        )

        try:
            result = run_query(
                question.strip(),
                pipeline=pipeline,
                retrieval_mode=retrieval_mode,
                top_k=top_k,
                ticker=ticker,
                report_year=report_year,
                model=model,
            )

            status.update(
                label="Analysis complete",
                state="complete",
                expanded=False,
            )

        except Exception as exc:
            status.update(
                label="Analysis failed",
                state="error",
            )

            st.exception(exc)
            st.stop()

    st.session_state[
        "financial_analysis_result"
    ] = result

    st.session_state[
        "financial_analysis_question"
    ] = question.strip()


# =============================================================
# Results
# =============================================================

if "financial_analysis_result" in st.session_state:
    result = st.session_state[
        "financial_analysis_result"
    ]

    question = st.session_state[
        "financial_analysis_question"
    ]

    st.divider()

    answer_tab, evidence_tab, tools_tab, diagnostics_tab = (
        st.tabs(
            [
                "💬 Answer",
                "📚 Evidence",
                "🛠 Agent trace",
                "📊 Diagnostics",
            ]
        )
    )

    # ---------------------------------------------------------
    # Answer
    # ---------------------------------------------------------

    with answer_tab:
        st.caption(
            (
                f"{result['pipeline'].upper()} · "
                f"{selected_ticker} · "
                f"{selected_year}"
            )
        )

        st.markdown(
            "### Financial analysis"
        )

        st.markdown(
            result["answer"]
        )

        timing = result.get(
            "timing",
            {},
        )

        total_time = timing.get(
            "total_seconds"
        )

        if total_time is not None:
            st.caption(
                f"Completed in {float(total_time):.2f} seconds"
            )

    # ---------------------------------------------------------
    # Evidence
    # ---------------------------------------------------------

    with evidence_tab:
        results = result.get(
            "results",
            [],
        )

        if not results:
            st.info(
                "No retrieval evidence is available."
            )

        else:
            left, right = st.columns(
                [1.7, 1]
            )

            with left:
                st.markdown(
                    f"### Retrieved evidence ({len(results)})"
                )

                for rank, source in enumerate(
                    results,
                    start=1,
                ):
                    display_source(
                        source,
                        rank,
                    )

            with right:
                frame = retrieval_dataframe(
                    results
                )

                st.markdown(
                    "### Retrieval overview"
                )

                if (
                    not frame.empty
                    and frame["Score"].notna().any()
                ):
                    chart_frame = (
                        frame.dropna(
                            subset=["Score"]
                        )
                        .copy()
                    )

                    chart_frame[
                        "Document"
                    ] = (
                        "#"
                        + chart_frame[
                            "Rank"
                        ].astype(str)
                        + " · "
                        + chart_frame[
                            "Ticker"
                        ].fillna("")
                        + " "
                        + chart_frame[
                            "Year"
                        ].fillna("").astype(str)
                    )

                    figure = px.bar(
                        chart_frame,
                        x="Score",
                        y="Document",
                        orientation="h",
                        title=(
                            "Retrieval ranking scores"
                        ),
                        hover_data=[
                            "Type",
                            "Section",
                        ],
                    )

                    figure.update_layout(
                        yaxis={
                            "categoryorder": (
                                "total ascending"
                            )
                        },
                        height=420,
                    )

                    st.plotly_chart(
                        figure,
                        use_container_width=True,
                    )

                type_counts = (
                    frame["Type"]
                    .fillna("unknown")
                    .value_counts()
                    .rename_axis(
                        "Content type"
                    )
                    .reset_index(
                        name="Documents"
                    )
                )

                if not type_counts.empty:
                    figure = px.pie(
                        type_counts,
                        names="Content type",
                        values="Documents",
                        hole=0.55,
                        title=(
                            "Retrieved content mix"
                        ),
                    )

                    st.plotly_chart(
                        figure,
                        use_container_width=True,
                    )

                st.dataframe(
                    frame,
                    use_container_width=True,
                    hide_index=True,
                )

    # ---------------------------------------------------------
    # Agent tools
    # ---------------------------------------------------------

    with tools_tab:
        if result["pipeline"] != "agent":
            st.info(
                "Tool traces are available when the "
                "Agent pipeline is selected."
            )

        else:
            tool_calls = result.get(
                "tool_calls",
                [],
            )

            cols = st.columns(2)

            cols[0].metric(
                "Additional tool calls",
                len(tool_calls),
            )

            successful = sum(
                1
                for call in tool_calls
                if _tool_status(call).lower()
                not in {
                    "failed",
                    "error",
                }
            )

            rate = (
                successful / len(tool_calls)
                if tool_calls
                else 1.0
            )

            cols[1].metric(
                "Tool success rate",
                f"{rate:.0%}",
            )

            display_tool_trace(
                tool_calls
            )

    # ---------------------------------------------------------
    # Diagnostics
    # ---------------------------------------------------------

    with diagnostics_tab:
        timing = result.get(
            "timing",
            {},
        )

        if timing:
            timing_rows = []

            for key, value in timing.items():
                if isinstance(
                    value,
                    (int, float),
                ):
                    timing_rows.append(
                        {
                            "Stage": (
                                key.replace(
                                    "_seconds",
                                    "",
                                )
                                .replace(
                                    "_",
                                    " ",
                                )
                                .title()
                            ),
                            "Seconds": value,
                        }
                    )

            if timing_rows:
                timing_frame = pd.DataFrame(
                    timing_rows
                )

                figure = px.bar(
                    timing_frame,
                    x="Stage",
                    y="Seconds",
                    title="Pipeline latency",
                )

                st.plotly_chart(
                    figure,
                    use_container_width=True,
                )

        with st.expander(
            "Retrieved context"
        ):
            st.code(
                result.get(
                    "context",
                    "",
                ),
                language="text",
            )

        with st.expander(
            "Raw execution result"
        ):
            raw = result.get(
                "raw_result",
                result,
            )

            try:
                st.json(raw)
            except Exception:
                st.code(
                    json.dumps(
                        raw,
                        indent=2,
                        default=str,
                    ),
                    language="json",
                )
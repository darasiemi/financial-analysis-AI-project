from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from deployment.frontend.api_client import (
    APIError,
    download_generated_file,
    get_filters,
    get_stats,
    run_analysis,
)


# =============================================================
# Paths
# =============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

FLASHCARDS_PATH = (
    PROJECT_ROOT
    / "data"
    / "frontend"
    / "company_flashcards.json"
)


# =============================================================
# Application configuration
# =============================================================

st.set_page_config(
    page_title="Financial Analysis AI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================
# Global styling
# =============================================================

st.html(
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
        line-height: 1.6;
    }

    .generated-file {
        padding: 1rem;
        border-radius: 14px;
        border:
            1px solid
            rgba(15, 118, 110, 0.24);
        background:
            rgba(15, 118, 110, 0.05);
        margin-top: 0.75rem;
        margin-bottom: 0.5rem;
    }

    div[data-testid="stMetric"] {
        border:
            1px solid
            rgba(148, 163, 184, 0.2);
        padding: 0.9rem;
        border-radius: 14px;
        background:
            rgba(248, 250, 252, 0.35);
    }
</style>
"""
)


# =============================================================
# Cached backend data
# =============================================================


@st.cache_data(ttl=300)
def load_filters() -> dict[str, Any]:
    """
    Load company and reporting-year filters from FastAPI.
    """

    return get_filters()


@st.cache_data(ttl=300)
def load_stats() -> dict[str, Any]:
    """
    Load corpus statistics from FastAPI.
    """

    return get_stats()


# =============================================================
# Flashcards
# =============================================================


@st.cache_data
def load_flashcards() -> list[dict[str, Any]]:
    """
    Load static company flashcards from:

    data/frontend/company_flashcards.json
    """

    try:
        with FLASHCARDS_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

    except FileNotFoundError:
        return []

    except json.JSONDecodeError:
        return []

    flashcards = data.get(
        "flashcards",
        [],
    )

    if not isinstance(
        flashcards,
        list,
    ):
        return []

    return [
        card
        for card in flashcards
        if isinstance(
            card,
            dict,
        )
    ]


def display_rotating_flashcards() -> None:
    """
    Display company fact flashcards that rotate
    automatically every 3 seconds.

    The animation runs entirely in the browser,
    so it continues while FastAPI processes the
    financial-analysis request.
    """

    flashcards = load_flashcards()

    if not flashcards:
        st.caption(
            "No company facts available."
        )
        return

    cards = flashcards.copy()

    random.shuffle(
        cards
    )

    total_cards = len(
        cards
    )

    seconds_per_card = 5

    animation_duration = (
        total_cards
        * seconds_per_card
    )

    visible_percent = (
        100
        / total_cards
    )

    fade_percent = min(
        1.2,
        visible_percent / 5,
    )

    card_html = ""

    for index, card in enumerate(
        cards
    ):
        company = str(
            card.get(
                "company",
                "Company",
            )
        )

        title = str(
            card.get(
                "title",
                "Did you know?",
            )
        )

        fact = str(
            card.get(
                "fact",
                "",
            )
        )

        category = str(
            card.get(
                "category",
                "",
            )
        )

        delay = (
            index
            * seconds_per_card
        )

        card_html += f"""
<div
    class="rotating-flashcard"
    style="
        animation-delay: {delay}s;
        animation-duration: {animation_duration}s;
    "
>
    <div class="flashcard-label">
        DID YOU KNOW?
    </div>

    <div class="flashcard-company">
        {company}
    </div>

    <div class="flashcard-title">
        {title}
    </div>

    <div class="flashcard-fact">
        {fact}
    </div>

    <div class="flashcard-category">
        {category}
    </div>
</div>
"""

    st.html(
        f"""
<style>
    .flashcard-rotator {{
        position: relative;
        width: 100%;
        min-height: 225px;
        margin-top: 0.75rem;
        margin-bottom: 0.5rem;
    }}

    .rotating-flashcard {{
        position: absolute;
        top: 0;
        left: 0;

        width: 100%;
        box-sizing: border-box;

        padding: 1.25rem 1.4rem;

        border-radius: 14px;

        background: #f8fafc;

        border:
            1px solid
            rgba(15, 118, 110, 0.20);

        border-left:
            4px solid
            #0f766e;

        opacity: 0;

        animation-name:
            rotateCompanyFact;

        animation-timing-function:
            linear;

        animation-iteration-count:
            infinite;
    }}

    @keyframes rotateCompanyFact {{

        0% {{
            opacity: 0;
        }}

        {fade_percent}% {{
            opacity: 1;
        }}

        {visible_percent - fade_percent}% {{
            opacity: 1;
        }}

        {visible_percent}% {{
            opacity: 0;
        }}

        100% {{
            opacity: 0;
        }}
    }}

    .flashcard-label {{
        font-size: 0.72rem;
        font-weight: 700;
        color: #0f766e;
        letter-spacing: 0.09em;
        margin-bottom: 0.35rem;
    }}

    .flashcard-company {{
        font-size: 0.82rem;
        font-weight: 600;
        color: #64748b;
        margin-bottom: 0.65rem;
    }}

    .flashcard-title {{
        font-size: 1.12rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.45rem;
    }}

    .flashcard-fact {{
        font-size: 0.95rem;
        line-height: 1.6;
        color: #334155;
    }}

    .flashcard-category {{
        display: inline-block;
        margin-top: 0.8rem;
        padding: 0.22rem 0.55rem;
        border-radius: 999px;

        background:
            rgba(
                15,
                118,
                110,
                0.09
            );

        color: #0f766e;

        font-size: 0.72rem;
        font-weight: 600;
    }}
</style>

<div class="flashcard-rotator">
    {card_html}
</div>
"""
    )


# =============================================================
# Generated files
# =============================================================


def display_generated_files(
    generated_files: list[
        dict[str, Any]
    ],
) -> None:
    """
    Display files produced by the agent
    as downloadable files.
    """

    if not generated_files:
        return

    st.markdown(
        "### Generated files"
    )

    for index, file_info in enumerate(
        generated_files,
        start=1,
    ):
        filename = file_info.get(
            "filename"
        )

        if not filename:
            continue

        file_type = file_info.get(
            "file_type",
            "file",
        )

        mime_type = (
            file_info.get(
                "mime_type"
            )
            or "application/octet-stream"
        )

        size_bytes = file_info.get(
            "size_bytes"
        )

        if file_type == "powerpoint":
            icon = "📊"
        else:
            icon = "📄"

        size_text = ""

        if size_bytes is not None:
            try:
                size_mb = (
                    float(size_bytes)
                    / 1024
                    / 1024
                )

                size_text = (
                    f"{size_mb:.2f} MB"
                )

            except (
                TypeError,
                ValueError,
            ):
                pass

        st.html(
            f"""
<div class="generated-file">
    <strong>
        {icon} {filename}
    </strong>
    <br>
    <span style="
        font-size: 0.82rem;
        opacity: 0.65;
    ">
        {size_text}
    </span>
</div>
"""
        )

        try:
            file_bytes = (
                download_generated_file(
                    filename
                )
            )

            st.download_button(
                label=(
                    f"Download {filename}"
                ),
                data=file_bytes,
                file_name=filename,
                mime=mime_type,
                width="stretch",
                key=(
                    f"download_"
                    f"{index}_"
                    f"{filename}"
                ),
            )

        except APIError as exc:
            st.error(
                (
                    "Could not download "
                    f"{filename}: {exc}"
                )
            )


# =============================================================
# Evidence helpers
# =============================================================


def display_source(
    result: dict[str, Any],
    rank: int,
) -> None:
    """
    Display one retrieved evidence item.
    """

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
            else (
                f"{page_start}"
                f"–{page_end}"
            )
        )

    else:
        pages = "—"

    with st.expander(
        (
            f"#{rank} · "
            f"{ticker} {year} · "
            f"{str(content_type).title()} · "
            f"Page {pages}"
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

        st.write(
            text
        )


def retrieval_dataframe(
    results: list[
        dict[str, Any]
    ],
) -> pd.DataFrame:
    """
    Convert retrieval results into a dataframe.
    """

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
                "Keyword Rank": (
                    result.get(
                        "keyword_rank"
                    )
                ),
                "Vector Rank": (
                    result.get(
                        "vector_rank"
                    )
                ),
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================
# Agent trace helpers
# =============================================================


def _tool_name(
    call: dict[str, Any],
) -> str:
    """
    Normalize tool name.
    """

    return str(
        call.get(
            "tool",
            call.get(
                "name",
                call.get(
                    "tool_name",
                    "Unknown tool",
                ),
            ),
        )
    )


def _tool_arguments(
    call: dict[str, Any],
) -> Any:
    """
    Normalize tool arguments.
    """

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
    """
    Infer tool status.
    """

    if call.get(
        "error"
    ):
        return "Failed"

    status = call.get(
        "status"
    )

    if status:
        return str(
            status
        )

    success = call.get(
        "success"
    )

    if success is False:
        return "Failed"

    if success is True:
        return "Success"

    response = call.get(
        "response",
        call.get(
            "result"
        ),
    )

    if isinstance(
        response,
        dict,
    ):
        response_success = (
            response.get(
                "success"
            )
        )

        if response_success is False:
            return "Failed"

        if response_success is True:
            return "Success"

    return "Completed"


def display_tool_trace(
    tool_calls: list[
        dict[str, Any]
    ],
) -> None:
    """
    Render agent tool calls.
    """

    if not tool_calls:
        st.info(
            "The agent did not invoke "
            "any additional tools."
        )
        return

    for index, call in enumerate(
        tool_calls,
        start=1,
    ):
        name = _tool_name(
            call
        )

        status = _tool_status(
            call
        )

        with st.expander(
            (
                f"Tool {index}: "
                f"{name} · {status}"
            ),
            expanded=index == 1,
        ):
            st.markdown(
                "**Arguments**"
            )

            arguments = (
                _tool_arguments(
                    call
                )
            )

            if isinstance(
                arguments,
                (dict, list),
            ):
                st.json(
                    arguments
                )

            else:
                st.code(
                    str(arguments),
                    language="text",
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
                    st.json(
                        response
                    )

                else:
                    st.code(
                        str(response),
                        language="text",
                    )

            error = call.get(
                "error"
            )

            if error:
                st.error(
                    str(error)
                )


# =============================================================
# Header
# =============================================================

st.html(
    """
<div class="hero">
    <h1>Financial Analysis AI</h1>

    <p>
        Ask analytical questions across corporate annual reports.
        Compare reported metrics, inspect retrieved evidence,
        reason over structured financial tables, generate
        presentation-ready analysis, and use an agentic workflow
        when additional tools are required.
    </p>
</div>
"""
)


# =============================================================
# Load backend metadata
# =============================================================

try:
    filters = load_filters()

    stats = load_stats()

except APIError as exc:
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
        "Backend metadata could not be loaded."
    )

    st.sidebar.caption(
        str(exc)
    )


# =============================================================
# Sidebar
# =============================================================

with st.sidebar:

    st.header(
        "Analysis settings"
    )

    pipeline_label = st.radio(
        "Pipeline",
        options=[
            "Agent",
            "RAG",
        ],
        horizontal=True,
    )

    pipeline = (
        pipeline_label.lower()
    )

    # ---------------------------------------------------------
    # Retrieval strategy
    # ---------------------------------------------------------

    if pipeline == "rag":

        retrieval_mode = st.selectbox(
            "Retrieval strategy",
            options=[
                "hybrid",
                "keyword",
                "vector",
            ],
            index=0,
            help=(
                "Choose how documents are retrieved "
                "for the standard RAG pipeline."
            ),
        )

    else:

        retrieval_mode = st.selectbox(
            "Retrieval strategy",
            options=[
                "hybrid",
            ],
            index=0,
            disabled=True,
            help=(
                "The Agent starts with hybrid retrieval "
                "and may invoke additional retrieval tools "
                "when required."
            ),
        )

    # ---------------------------------------------------------
    # Company
    # ---------------------------------------------------------

    ticker_options = [
        "All companies",
        *filters.get(
            "tickers",
            [],
        ),
    ]

    selected_ticker = st.selectbox(
        "Company",
        ticker_options,
    )

    ticker = (
        None
        if selected_ticker
        == "All companies"
        else selected_ticker
    )

    # ---------------------------------------------------------
    # Report year
    # ---------------------------------------------------------

    year_options = [
        "All years",
        *filters.get(
            "years",
            [],
        ),
    ]

    selected_year = st.selectbox(
        "Report year",
        year_options,
    )

    report_year = (
        None
        if selected_year == "All years"
        else int(
            selected_year
        )
    )

    # ---------------------------------------------------------
    # Top K
    # ---------------------------------------------------------

    top_k = st.slider(
        "Top-K evidence",
        min_value=3,
        max_value=15,
        value=8,
        step=1,
    )

    # ---------------------------------------------------------
    # Model
    # ---------------------------------------------------------

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

metric_columns = st.columns(
    5
)

metric_columns[0].metric(
    "Indexed documents",
    f"{stats.get('documents', 0):,}",
)

metric_columns[1].metric(
    "Companies",
    stats.get(
        "companies",
        0,
    ),
)

metric_columns[2].metric(
    "Report years",
    stats.get(
        "years",
        0,
    ),
)

metric_columns[3].metric(
    "Narrative",
    f"{stats.get('narratives', 0):,}",
)

metric_columns[4].metric(
    "Tables",
    f"{stats.get('tables', 0):,}",
)


# =============================================================
# Question form
# =============================================================

st.subheader(
    "Ask a financial question"
)

examples = [
    (
        "Compare GTCO's profit before tax "
        "in 2023 and 2024 and calculate "
        "the percentage increase."
    ),
    (
        "How did Zenith Bank's gross loans "
        "change from 2023 to 2024?"
    ),
    (
        "Compare MTN Nigeria's profitability "
        "across the available reporting periods."
    ),
    (
        "Create a PowerPoint presentation "
        "comparing GTCO's profit before tax "
        "in 2023 and 2024, calculate the "
        "percentage increase, and save the "
        "presentation."
    ),
]

example = st.selectbox(
    "Example questions",
    [
        "Write my own question",
        *examples,
    ],
)

default_question = (
    ""
    if example
    == "Write my own question"
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
            "e.g. Compare GTCO's profit "
            "before tax in 2023 and 2024 "
            "and calculate the percentage "
            "increase."
        ),
    )

    submitted = (
        st.form_submit_button(
            "Run financial analysis",
            type="primary",
            width="stretch",
        )
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

        # Flashcards rotate every 3 seconds in the browser.
        display_rotating_flashcards()

        try:

            result = run_analysis(
                question.strip(),
                pipeline=pipeline,
                retrieval_mode=(
                    retrieval_mode
                ),
                top_k=top_k,
                ticker=ticker,
                report_year=(
                    report_year
                ),
                model=model,
            )

            status.update(
                label="Analysis complete",
                state="complete",
                expanded=False,
            )

        except APIError as exc:

            status.update(
                label="Analysis failed",
                state="error",
                expanded=True,
            )

            st.error(
                str(exc)
            )

            st.stop()

        except Exception as exc:

            status.update(
                label="Analysis failed",
                state="error",
                expanded=True,
            )

            st.exception(
                exc
            )

            st.stop()

    st.session_state[
        "financial_analysis_result"
    ] = result

    st.session_state[
        "financial_analysis_question"
    ] = question.strip()

    st.session_state[
        "financial_analysis_ticker"
    ] = selected_ticker

    st.session_state[
        "financial_analysis_year"
    ] = selected_year


# =============================================================
# Results
# =============================================================

if (
    "financial_analysis_result"
    in st.session_state
):

    result = (
        st.session_state[
            "financial_analysis_result"
        ]
    )

    result_ticker = (
        st.session_state.get(
            "financial_analysis_ticker",
            selected_ticker,
        )
    )

    result_year = (
        st.session_state.get(
            "financial_analysis_year",
            selected_year,
        )
    )

    st.divider()

    (
        answer_tab,
        evidence_tab,
        tools_tab,
        diagnostics_tab,
    ) = st.tabs(
        [
            "💬 Answer",
            "📚 Evidence",
            "🛠 Agent trace",
            "📊 Diagnostics",
        ]
    )


    # =========================================================
    # Answer
    # =========================================================

    with answer_tab:

        st.caption(
            (
                f"{str(result.get('pipeline', '')).upper()} · "
                f"{result_ticker} · "
                f"{result_year}"
            )
        )

        st.markdown(
            "### Financial analysis"
        )

        answer = result.get(
            "answer",
            "No answer was returned.",
        )

        st.markdown(
            answer
        )

        display_generated_files(
            result.get(
                "generated_files",
                [],
            )
        )

        timing = result.get(
            "timing",
            {},
        )

        total_time = timing.get(
            "total_seconds"
        )

        if total_time is not None:
            try:
                st.caption(
                    (
                        "Completed in "
                        f"{float(total_time):.2f} "
                        "seconds"
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                pass


    # =========================================================
    # Evidence
    # =========================================================

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

            left, right = (
                st.columns(
                    [1.7, 1]
                )
            )

            with left:

                st.markdown(
                    (
                        "### Retrieved evidence "
                        f"({len(results)})"
                    )
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

                frame = (
                    retrieval_dataframe(
                        results
                    )
                )

                st.markdown(
                    "### Retrieval overview"
                )

                if (
                    not frame.empty
                    and "Score"
                    in frame.columns
                    and frame[
                        "Score"
                    ]
                    .notna()
                    .any()
                ):

                    chart_frame = (
                        frame.dropna(
                            subset=[
                                "Score"
                            ]
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
                        ]
                        .fillna("")
                        .astype(str)
                        + " "
                        + chart_frame[
                            "Year"
                        ]
                        .fillna("")
                        .astype(str)
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
                            "categoryorder":
                            "total ascending"
                        },
                        height=420,
                    )

                    st.plotly_chart(
                        figure,
                        width="stretch",
                    )

                if (
                    not frame.empty
                    and "Type"
                    in frame.columns
                ):

                    type_counts = (
                        frame[
                            "Type"
                        ]
                        .fillna(
                            "unknown"
                        )
                        .value_counts()
                        .rename_axis(
                            "Content type"
                        )
                        .reset_index(
                            name="Documents"
                        )
                    )

                    if (
                        not type_counts.empty
                    ):

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
                            width="stretch",
                        )

                st.dataframe(
                    frame,
                    width="stretch",
                    hide_index=True,
                )


    # =========================================================
    # Agent trace
    # =========================================================

    with tools_tab:

        if (
            result.get(
                "pipeline"
            )
            != "agent"
        ):

            st.info(
                "Tool traces are available "
                "when the Agent pipeline "
                "is selected."
            )

        else:

            tool_calls = result.get(
                "tool_calls",
                [],
            )

            cols = st.columns(
                2
            )

            cols[0].metric(
                "Additional tool calls",
                len(
                    tool_calls
                ),
            )

            successful = sum(
                1
                for call in tool_calls
                if (
                    _tool_status(
                        call
                    ).lower()
                    not in {
                        "failed",
                        "error",
                    }
                )
            )

            rate = (
                successful
                / len(
                    tool_calls
                )
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


    # =========================================================
    # Diagnostics
    # =========================================================

    with diagnostics_tab:

        timing = result.get(
            "timing",
            {},
        )

        if timing:

            timing_rows = []

            for key, value in (
                timing.items()
            ):

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

                timing_frame = (
                    pd.DataFrame(
                        timing_rows
                    )
                )

                figure = px.bar(
                    timing_frame,
                    x="Stage",
                    y="Seconds",
                    title="Pipeline latency",
                )

                st.plotly_chart(
                    figure,
                    width="stretch",
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
                st.json(
                    raw
                )

            except Exception:

                st.code(
                    json.dumps(
                        raw,
                        indent=2,
                        default=str,
                    ),
                    language="json",
                )
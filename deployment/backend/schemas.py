from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    Field,
)


PipelineType = Literal[
    "rag",
    "agent",
]

RetrievalMode = Literal[
    "keyword",
    "vector",
    "hybrid",
]


class QueryRequest(
    BaseModel
):
    question: str = Field(
        min_length=1,
        max_length=4000,
    )

    session_id: str

    pipeline: PipelineType = (
        "agent"
    )

    retrieval_mode: RetrievalMode = (
        "hybrid"
    )

    top_k: int = Field(
        default=8,
        ge=1,
        le=50,
    )

    ticker: str | None = None

    report_year: int | None = None

    model: str = (
        "gemini-2.5-flash"
    )


class GeneratedFile(
    BaseModel
):
    filename: str
    file_type: str
    format: str
    mime_type: str
    size_bytes: int | None = None


class QueryResponse(
    BaseModel
):
    response_id: str

    pipeline: str

    answer: str

    results: list[
        dict[str, Any]
    ] = Field(
        default_factory=list
    )

    context: str = ""

    tool_calls: list[
        dict[str, Any]
    ] = Field(
        default_factory=list
    )

    generated_files: list[
        GeneratedFile
    ] = Field(
        default_factory=list
    )

    timing: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    estimated_cost_usd: float = 0.0


class FeedbackRequest(
    BaseModel
):
    response_id: str

    rating: Literal[
        -1,
        1,
    ]


class FeedbackResponse(
    BaseModel
):
    success: bool


class FiltersResponse(
    BaseModel
):
    tickers: list[str]
    years: list[int]


class CorpusStatsResponse(
    BaseModel
):
    documents: int
    companies: int
    years: int
    tables: int
    narratives: int


class HealthResponse(
    BaseModel
):
    status: str
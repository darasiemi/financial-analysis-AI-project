from __future__ import annotations

import logging
import time
import uuid

from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
)
from fastapi.responses import (
    FileResponse,
)

from deployment.backend.database import (
    database_is_available,
    get_available_filters,
    get_corpus_stats,
)
from deployment.backend.files import (
    get_generated_file_path,
)
from deployment.backend.schemas import (
    CorpusStatsResponse,
    FeedbackRequest,
    FeedbackResponse,
    FiltersResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
)
from deployment.backend.service import (
    run_query,
)
from monitoring.database import (
    ensure_monitoring_schema,
    save_failed_interaction,
    save_feedback,
    save_interaction,
)
from monitoring.judge import (
    judge_relevance_background,
)
from monitoring.telemetry import (
    monitoring_context,
)

logger = logging.getLogger(__name__)


app = FastAPI(
    title="Financial Analysis API",
    description=(
        "RAG and agentic financial analysis " "over corporate annual reports."
    ),
    version="0.2.0",
)


@app.on_event("startup")
def startup() -> None:
    ensure_monitoring_schema()


@app.get(
    "/health",
    response_model=HealthResponse,
)
def health() -> HealthResponse:

    if not database_is_available():
        raise HTTPException(
            status_code=503,
            detail=("Database is unavailable."),
        )

    return HealthResponse(status="healthy")


@app.get(
    "/api/v1/filters",
    response_model=FiltersResponse,
)
def filters() -> FiltersResponse:

    return FiltersResponse(**get_available_filters())


@app.get(
    "/api/v1/stats",
    response_model=(CorpusStatsResponse),
)
def stats() -> CorpusStatsResponse:

    return CorpusStatsResponse(**get_corpus_stats())


@app.post(
    "/api/v1/query",
    response_model=QueryResponse,
)
def query(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
) -> QueryResponse:

    response_id = str(uuid.uuid4())

    request_start = time.perf_counter()

    try:

        with monitoring_context(response_id) as telemetry:

            result = run_query(
                request.question,
                pipeline=request.pipeline,
                retrieval_mode=(request.retrieval_mode),
                top_k=request.top_k,
                ticker=request.ticker,
                report_year=(request.report_year),
                model=request.model,
            )

            total_latency = time.perf_counter() - request_start

            timing = dict(
                result.get(
                    "timing",
                    {},
                )
            )

            timing["api_total_seconds"] = total_latency

            answer = result.get(
                "answer",
                "",
            )

            save_interaction(
                response_id=response_id,
                session_id=request.session_id,
                question=request.question,
                answer=answer,
                pipeline=request.pipeline,
                retrieval_mode=(request.retrieval_mode),
                ticker=request.ticker,
                report_year=(request.report_year),
                model=request.model,
                total_latency_seconds=(total_latency),
                latencies=timing,
                telemetry=telemetry,
            )

            # -----------------------------------------------
            # Runs AFTER response is returned to Streamlit.
            # -----------------------------------------------

            background_tasks.add_task(
                judge_relevance_background,
                response_id=response_id,
                question=request.question,
                answer=answer,
            )

            return QueryResponse(
                response_id=response_id,
                pipeline=result.get(
                    "pipeline",
                    request.pipeline,
                ),
                answer=answer,
                results=result.get(
                    "results",
                    [],
                ),
                context=result.get(
                    "context",
                    "",
                ),
                tool_calls=result.get(
                    "tool_calls",
                    [],
                ),
                generated_files=(
                    result.get(
                        "generated_files",
                        [],
                    )
                ),
                timing=timing,
                estimated_cost_usd=(telemetry.estimated_cost_usd),
            )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        total_latency = time.perf_counter() - request_start

        try:

            save_failed_interaction(
                response_id=response_id,
                session_id=request.session_id,
                question=request.question,
                pipeline=request.pipeline,
                retrieval_mode=(request.retrieval_mode),
                model=request.model,
                latency_seconds=(total_latency),
                error=str(exc),
            )

        except Exception:
            logger.exception("Could not persist failed interaction.")

        logger.exception("Financial analysis failed.")

        raise HTTPException(
            status_code=500,
            detail=("Financial analysis could " "not be completed."),
        ) from exc


@app.post(
    "/api/v1/feedback",
    response_model=FeedbackResponse,
)
def feedback(
    request: FeedbackRequest,
) -> FeedbackResponse:

    try:

        save_feedback(
            response_id=(request.response_id),
            rating=request.rating,
        )

        return FeedbackResponse(success=True)

    except Exception as exc:

        logger.exception("Could not save feedback.")

        raise HTTPException(
            status_code=500,
            detail=("Could not save feedback."),
        ) from exc


@app.get(
    "/api/v1/files/{filename}",
)
def download_generated_file(
    filename: str,
) -> FileResponse:

    try:
        file_path = get_generated_file_path(filename)

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail="Invalid filename.",
        ) from exc

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    return FileResponse(
        path=file_path,
        filename=file_path.name,
    )

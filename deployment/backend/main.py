from __future__ import annotations

import logging

from fastapi import (
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
    FiltersResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
)
from deployment.backend.service import (
    run_query,
)


logger = logging.getLogger(
    __name__
)


app = FastAPI(
    title="Financial Analysis API",
    description=(
        "RAG and agentic financial "
        "analysis over corporate "
        "annual reports."
    ),
    version="0.1.0",
)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
)
def health() -> HealthResponse:

    if not database_is_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "Database is unavailable."
            ),
        )

    return HealthResponse(
        status="healthy"
    )


@app.get(
    "/api/v1/filters",
    response_model=FiltersResponse,
    tags=["Metadata"],
)
def filters() -> FiltersResponse:

    try:
        result = (
            get_available_filters()
        )

        return FiltersResponse(
            **result
        )

    except Exception as exc:
        logger.exception(
            "Failed to load filters."
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to load "
                "corpus filters."
            ),
        ) from exc


@app.get(
    "/api/v1/stats",
    response_model=(
        CorpusStatsResponse
    ),
    tags=["Metadata"],
)
def stats() -> CorpusStatsResponse:

    try:
        result = (
            get_corpus_stats()
        )

        return CorpusStatsResponse(
            **result
        )

    except Exception as exc:
        logger.exception(
            "Failed to load "
            "corpus statistics."
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to load "
                "corpus statistics."
            ),
        ) from exc


@app.post(
    "/api/v1/query",
    response_model=QueryResponse,
    tags=["Analysis"],
)
def query(
    request: QueryRequest,
) -> QueryResponse:

    try:
        result = run_query(
            request.question,
            pipeline=request.pipeline,
            retrieval_mode=(
                request.retrieval_mode
            ),
            top_k=request.top_k,
            ticker=request.ticker,
            report_year=(
                request.report_year
            ),
            model=request.model,
        )

        return QueryResponse(
            **result
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Financial analysis failed."
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Financial analysis "
                "could not be completed."
            ),
        ) from exc


@app.get(
    "/api/v1/files/{filename}",
    tags=["Files"],
)
def download_generated_file(
    filename: str,
) -> FileResponse:
    """
    Download a generated PowerPoint.
    """

    try:
        file_path = (
            get_generated_file_path(
                filename
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename.",
        ) from exc

    if (
        not file_path.exists()
        or not file_path.is_file()
    ):
        raise HTTPException(
            status_code=404,
            detail=(
                "Generated presentation "
                "was not found."
            ),
        )

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "presentationml.presentation"
        ),
    )
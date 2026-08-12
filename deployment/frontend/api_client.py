from __future__ import annotations

import os
from typing import Any

import requests


# =============================================================
# Configuration
# =============================================================

API_BASE_URL = os.getenv(
    "FASTAPI_BASE_URL",
    "http://localhost:8000",
).rstrip("/")


QUERY_TIMEOUT = 300

DOWNLOAD_TIMEOUT = 120


# =============================================================
# Errors
# =============================================================


class APIError(
    RuntimeError
):
    """
    Error communicating with the
    FastAPI backend.
    """

    pass


# =============================================================
# Response handling
# =============================================================


def _error_detail(
    response: requests.Response,
) -> str:
    """
    Extract a useful error message from
    a FastAPI response.
    """

    try:
        payload = (
            response.json()
        )

        if isinstance(
            payload,
            dict,
        ):
            return str(
                payload.get(
                    "detail",
                    response.text,
                )
            )

    except ValueError:
        pass

    return (
        response.text
        or response.reason
        or "Unknown backend error."
    )


def _handle_json_response(
    response: requests.Response,
) -> dict[str, Any]:
    """
    Validate and parse a JSON response.
    """

    try:
        response.raise_for_status()

    except requests.HTTPError as exc:
        raise APIError(
            _error_detail(
                response
            )
        ) from exc

    try:
        payload = (
            response.json()
        )

    except ValueError as exc:
        raise APIError(
            "Backend returned an "
            "invalid JSON response."
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise APIError(
            "Backend returned an "
            "unexpected response."
        )

    return payload


# =============================================================
# Health
# =============================================================


def get_health() -> dict[str, Any]:
    """
    Check FastAPI backend health.
    """

    try:
        response = requests.get(
            (
                f"{API_BASE_URL}"
                "/health"
            ),
            timeout=10,
        )

    except requests.RequestException as exc:
        raise APIError(
            "FastAPI backend is "
            "unavailable."
        ) from exc

    return _handle_json_response(
        response
    )


# =============================================================
# Metadata
# =============================================================


def get_filters() -> dict[str, Any]:
    """
    Retrieve company/year filters.
    """

    try:
        response = requests.get(
            (
                f"{API_BASE_URL}"
                "/api/v1/filters"
            ),
            timeout=30,
        )

    except requests.RequestException as exc:
        raise APIError(
            "Unable to reach "
            "the backend."
        ) from exc

    return _handle_json_response(
        response
    )


def get_stats() -> dict[str, Any]:
    """
    Retrieve corpus statistics.
    """

    try:
        response = requests.get(
            (
                f"{API_BASE_URL}"
                "/api/v1/stats"
            ),
            timeout=30,
        )

    except requests.RequestException as exc:
        raise APIError(
            "Unable to reach "
            "the backend."
        ) from exc

    return _handle_json_response(
        response
    )


# =============================================================
# Financial analysis
# =============================================================


def run_analysis(
    question: str,
    *,
    pipeline: str,
    retrieval_mode: str,
    top_k: int,
    ticker: str | None,
    report_year: int | None,
    model: str,
) -> dict[str, Any]:
    """
    Execute a financial-analysis request
    through FastAPI.
    """

    payload = {
        "question": question,
        "pipeline": pipeline,
        "retrieval_mode": (
            retrieval_mode
        ),
        "top_k": top_k,
        "ticker": ticker,
        "report_year": (
            report_year
        ),
        "model": model,
    }

    try:
        response = requests.post(
            (
                f"{API_BASE_URL}"
                "/api/v1/query"
            ),
            json=payload,
            timeout=QUERY_TIMEOUT,
        )

    except requests.Timeout as exc:
        raise APIError(
            "The analysis request "
            "timed out."
        ) from exc

    except requests.RequestException as exc:
        raise APIError(
            "The connection to the "
            "FastAPI backend was lost."
        ) from exc

    return _handle_json_response(
        response
    )


# =============================================================
# Generated files
# =============================================================


def download_generated_file(
    filename: str,
) -> bytes:
    """
    Download a generated report from
    the FastAPI backend.
    """

    try:
        response = requests.get(
            (
                f"{API_BASE_URL}"
                f"/api/v1/files/"
                f"{filename}"
            ),
            timeout=DOWNLOAD_TIMEOUT,
        )

        response.raise_for_status()

    except requests.HTTPError as exc:
        raise APIError(
            _error_detail(
                response
            )
        ) from exc

    except requests.RequestException as exc:
        raise APIError(
            "Unable to download "
            f"{filename}."
        ) from exc

    return response.content
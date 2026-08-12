from __future__ import annotations

import os
from typing import Any

import requests


API_BASE_URL = os.getenv(
    "FASTAPI_BASE_URL",
    "http://localhost:8000",
).rstrip("/")


DEFAULT_TIMEOUT = 180


class APIError(RuntimeError):
    pass


def _handle_response(
    response: requests.Response,
) -> dict[str, Any]:

    try:
        response.raise_for_status()

    except requests.HTTPError as exc:
        try:
            payload = response.json()

            detail = payload.get(
                "detail",
                str(exc),
            )

        except ValueError:
            detail = (
                response.text
                or str(exc)
            )

        raise APIError(
            f"API request failed: {detail}"
        ) from exc

    return response.json()


def get_health() -> dict[str, Any]:
    response = requests.get(
        f"{API_BASE_URL}/health",
        timeout=10,
    )

    return _handle_response(
        response
    )


def get_filters() -> dict[str, Any]:
    response = requests.get(
        f"{API_BASE_URL}/api/v1/filters",
        timeout=30,
    )

    return _handle_response(
        response
    )


def get_stats() -> dict[str, Any]:
    response = requests.get(
        f"{API_BASE_URL}/api/v1/stats",
        timeout=30,
    )

    return _handle_response(
        response
    )


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

    payload = {
        "question": question,
        "pipeline": pipeline,
        "retrieval_mode": retrieval_mode,
        "top_k": top_k,
        "ticker": ticker,
        "report_year": report_year,
        "model": model,
    }

    response = requests.post(
        f"{API_BASE_URL}/api/v1/query",
        json=payload,
        timeout=DEFAULT_TIMEOUT,
    )

    return _handle_response(
        response
    )
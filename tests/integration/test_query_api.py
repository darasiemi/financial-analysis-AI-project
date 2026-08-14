from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from deployment.backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _mock_result(
    pipeline: str,
) -> dict:
    return {
        "pipeline": pipeline,
        "answer": ("This is a mocked financial " "analysis response."),
        "results": [],
        "context": "",
        "tool_calls": [],
        "generated_files": [],
        "timing": {
            "total_seconds": 0.1,
        },
    }


def _payload(
    pipeline: str,
) -> dict:
    return {
        "question": ("What was GTCO's profit " "before tax in 2025?"),
        "session_id": str(uuid.uuid4()),
        "pipeline": pipeline,
        "retrieval_mode": "hybrid",
        "top_k": 8,
        "ticker": None,
        "report_year": None,
        "model": "gemini-2.5-flash",
    }


def test_rag_query(
    client,
    monkeypatch,
) -> None:

    def fake_run_query(
        _question,
        **_kwargs,
    ):
        return _mock_result("rag")

    monkeypatch.setattr(
        "deployment.backend.main.run_query",
        fake_run_query,
    )

    monkeypatch.setattr(
        ("deployment.backend.main." "judge_relevance_background"),
        lambda **_kwargs: None,
    )

    response = client.post(
        "/api/v1/query",
        json=_payload("rag"),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["pipeline"] == "rag"
    assert data["answer"]
    assert data["response_id"]


def test_agent_query(
    client,
    monkeypatch,
) -> None:

    def fake_run_query(
        _question,
        **_kwargs,
    ):
        return _mock_result("agent")

    monkeypatch.setattr(
        "deployment.backend.main.run_query",
        fake_run_query,
    )

    monkeypatch.setattr(
        ("deployment.backend.main." "judge_relevance_background"),
        lambda **_kwargs: None,
    )

    response = client.post(
        "/api/v1/query",
        json=_payload("agent"),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["pipeline"] == "agent"
    assert data["answer"]
    assert data["response_id"]

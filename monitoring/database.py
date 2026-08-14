from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ingestion.processing.database import (
    get_postgres_connection_string,
    load_environment,
)
from monitoring.telemetry import (
    RequestTelemetry,
)


def _connection_string() -> str:
    load_environment()

    return get_postgres_connection_string()


def ensure_monitoring_schema() -> None:
    """
    Create monitoring tables if they do not exist.
    """

    sql = """
    CREATE SCHEMA IF NOT EXISTS monitoring;

    CREATE TABLE IF NOT EXISTS monitoring.sessions (
        session_id UUID PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS monitoring.interactions (
        response_id UUID PRIMARY KEY,

        session_id UUID REFERENCES monitoring.sessions(session_id),

        question TEXT NOT NULL,
        answer TEXT,

        pipeline TEXT NOT NULL,
        retrieval_mode TEXT,

        ticker TEXT,
        report_year INTEGER,

        model TEXT NOT NULL,

        status TEXT NOT NULL DEFAULT 'completed',

        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ,

        total_latency_seconds DOUBLE PRECISION,

        latencies JSONB NOT NULL DEFAULT '{}'::jsonb,

        application_input_tokens INTEGER NOT NULL DEFAULT 0,
        application_output_tokens INTEGER NOT NULL DEFAULT 0,
        application_thinking_tokens INTEGER NOT NULL DEFAULT 0,
        application_total_tokens INTEGER NOT NULL DEFAULT 0,

        application_cost_usd NUMERIC(16, 10)
            NOT NULL DEFAULT 0,

        judge_sampled BOOLEAN NOT NULL DEFAULT FALSE,

        relevance_score DOUBLE PRECISION,
        relevance_reason TEXT,

        judge_model TEXT,
        judge_latency_seconds DOUBLE PRECISION,

        judge_input_tokens INTEGER,
        judge_output_tokens INTEGER,
        judge_thinking_tokens INTEGER,
        judge_total_tokens INTEGER,

        judge_cost_usd NUMERIC(16, 10)
            NOT NULL DEFAULT 0,

        judge_status TEXT NOT NULL DEFAULT 'pending',

        error_text TEXT
    );

    CREATE TABLE IF NOT EXISTS monitoring.llm_calls (
        id BIGSERIAL PRIMARY KEY,

        response_id UUID NOT NULL
            REFERENCES monitoring.interactions(response_id)
            ON DELETE CASCADE,

        purpose TEXT NOT NULL,

        model TEXT NOT NULL,

        input_tokens INTEGER NOT NULL DEFAULT 0,
        output_tokens INTEGER NOT NULL DEFAULT 0,
        thinking_tokens INTEGER NOT NULL DEFAULT 0,
        total_tokens INTEGER NOT NULL DEFAULT 0,

        estimated_cost_usd NUMERIC(16, 10)
            NOT NULL DEFAULT 0,

        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS monitoring.feedback (
        response_id UUID PRIMARY KEY
            REFERENCES monitoring.interactions(response_id)
            ON DELETE CASCADE,

        rating SMALLINT NOT NULL
            CHECK (rating IN (-1, 1)),

        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS
        monitoring_interactions_created_idx
        ON monitoring.interactions(created_at);

    CREATE INDEX IF NOT EXISTS
        monitoring_interactions_pipeline_idx
        ON monitoring.interactions(pipeline);

    CREATE INDEX IF NOT EXISTS
        monitoring_relevance_idx
        ON monitoring.interactions(relevance_score);

    CREATE INDEX IF NOT EXISTS
        monitoring_llm_calls_response_idx
        ON monitoring.llm_calls(response_id);


    CREATE OR REPLACE VIEW
        monitoring.response_monitoring
    AS

    SELECT
        i.response_id,
        i.session_id,
        i.created_at,
        i.question,
        i.answer,
        i.pipeline,
        i.retrieval_mode,
        i.ticker,
        i.report_year,
        i.model,

        i.total_latency_seconds,

        i.application_total_tokens,
        i.application_cost_usd,

        i.relevance_score,
        i.judge_cost_usd,
        i.judge_status,

        f.rating AS user_feedback

    FROM monitoring.interactions i

    LEFT JOIN monitoring.feedback f
        ON f.response_id = i.response_id;
    """

    with psycopg.connect(_connection_string()) as connection:

        with connection.cursor() as cursor:
            cursor.execute(sql)

        connection.commit()


def save_interaction(
    *,
    response_id: str,
    session_id: str,
    question: str,
    answer: str,
    pipeline: str,
    retrieval_mode: str,
    ticker: str | None,
    report_year: int | None,
    model: str,
    total_latency_seconds: float,
    latencies: dict[str, Any],
    telemetry: RequestTelemetry,
) -> None:
    """
    Persist the conversation and application telemetry.
    """

    now = datetime.now(timezone.utc)

    with psycopg.connect(_connection_string()) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO monitoring.sessions (
                    session_id,
                    created_at,
                    last_seen_at
                )
                VALUES (
                    %s,
                    %s,
                    %s
                )
                ON CONFLICT (session_id)
                DO UPDATE SET
                    last_seen_at = EXCLUDED.last_seen_at;
                """,
                (
                    session_id,
                    now,
                    now,
                ),
            )

            cursor.execute(
                """
                INSERT INTO monitoring.interactions (
                    response_id,
                    session_id,
                    question,
                    answer,
                    pipeline,
                    retrieval_mode,
                    ticker,
                    report_year,
                    model,
                    status,
                    created_at,
                    completed_at,
                    total_latency_seconds,
                    latencies,
                    application_input_tokens,
                    application_output_tokens,
                    application_thinking_tokens,
                    application_total_tokens,
                    application_cost_usd,
                    judge_status
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    'completed',
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    'pending'
                );
                """,
                (
                    response_id,
                    session_id,
                    question,
                    answer,
                    pipeline,
                    retrieval_mode,
                    ticker,
                    report_year,
                    model,
                    now,
                    now,
                    total_latency_seconds,
                    Jsonb(latencies),
                    telemetry.input_tokens,
                    telemetry.output_tokens,
                    telemetry.thinking_tokens,
                    telemetry.total_tokens,
                    telemetry.estimated_cost_usd,
                ),
            )

            for call in telemetry.llm_calls:

                cursor.execute(
                    """
                    INSERT INTO monitoring.llm_calls (
                        response_id,
                        purpose,
                        model,
                        input_tokens,
                        output_tokens,
                        thinking_tokens,
                        total_tokens,
                        estimated_cost_usd
                    )
                    VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s
                    );
                    """,
                    (
                        response_id,
                        call.purpose,
                        call.model,
                        call.input_tokens,
                        call.output_tokens,
                        call.thinking_tokens,
                        call.total_tokens,
                        call.estimated_cost_usd,
                    ),
                )

        connection.commit()


def save_failed_interaction(
    *,
    response_id: str,
    session_id: str,
    question: str,
    pipeline: str,
    retrieval_mode: str,
    model: str,
    latency_seconds: float,
    error: str,
) -> None:

    now = datetime.now(timezone.utc)

    with psycopg.connect(_connection_string()) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO monitoring.sessions (
                    session_id
                )
                VALUES (%s)
                ON CONFLICT (session_id)
                DO UPDATE SET
                    last_seen_at = NOW();
                """,
                (session_id,),
            )

            cursor.execute(
                """
                INSERT INTO monitoring.interactions (
                    response_id,
                    session_id,
                    question,
                    pipeline,
                    retrieval_mode,
                    model,
                    status,
                    created_at,
                    completed_at,
                    total_latency_seconds,
                    error_text,
                    judge_status
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, 'failed',
                    %s, %s, %s, %s,
                    'not_run'
                );
                """,
                (
                    response_id,
                    session_id,
                    question,
                    pipeline,
                    retrieval_mode,
                    model,
                    now,
                    now,
                    latency_seconds,
                    error,
                ),
            )

        connection.commit()


def save_feedback(
    *,
    response_id: str,
    rating: int,
) -> None:
    """
    rating:
        +1 = thumbs up
        -1 = thumbs down
    """

    if rating not in {
        -1,
        1,
    }:
        raise ValueError("Feedback must be -1 or 1.")

    with psycopg.connect(_connection_string()) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO monitoring.feedback (
                    response_id,
                    rating
                )
                VALUES (
                    %s,
                    %s
                )
                ON CONFLICT (response_id)
                DO UPDATE SET
                    rating = EXCLUDED.rating,
                    updated_at = NOW();
                """,
                (
                    response_id,
                    rating,
                ),
            )

        connection.commit()


def save_judge_result(
    *,
    response_id: str,
    score: float,
    reason: str,
    model: str,
    latency_seconds: float,
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int,
    total_tokens: int,
    cost_usd: float,
) -> None:

    with psycopg.connect(_connection_string()) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE monitoring.interactions

                SET
                    judge_sampled = TRUE,
                    relevance_score = %s,
                    relevance_reason = %s,
                    judge_model = %s,
                    judge_latency_seconds = %s,
                    judge_input_tokens = %s,
                    judge_output_tokens = %s,
                    judge_thinking_tokens = %s,
                    judge_total_tokens = %s,
                    judge_cost_usd = %s,
                    judge_status = 'completed'

                WHERE response_id = %s;
                """,
                (
                    score,
                    reason,
                    model,
                    latency_seconds,
                    input_tokens,
                    output_tokens,
                    thinking_tokens,
                    total_tokens,
                    cost_usd,
                    response_id,
                ),
            )

            cursor.execute(
                """
                INSERT INTO monitoring.llm_calls (
                    response_id,
                    purpose,
                    model,
                    input_tokens,
                    output_tokens,
                    thinking_tokens,
                    total_tokens,
                    estimated_cost_usd
                )
                VALUES (
                    %s,
                    'judge',
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                );
                """,
                (
                    response_id,
                    model,
                    input_tokens,
                    output_tokens,
                    thinking_tokens,
                    total_tokens,
                    cost_usd,
                ),
            )

        connection.commit()


def mark_judge_skipped(
    response_id: str,
) -> None:

    with psycopg.connect(_connection_string()) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE monitoring.interactions

                SET
                    judge_sampled = FALSE,
                    judge_status = 'skipped'

                WHERE response_id = %s;
                """,
                (response_id,),
            )

        connection.commit()


def mark_judge_failed(
    *,
    response_id: str,
    error: str,
) -> None:

    with psycopg.connect(_connection_string()) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE monitoring.interactions

                SET
                    judge_sampled = TRUE,
                    judge_status = 'failed',
                    relevance_reason = %s

                WHERE response_id = %s;
                """,
                (
                    error,
                    response_id,
                ),
            )

        connection.commit()

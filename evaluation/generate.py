import json
import random
import re
import uuid
from collections import defaultdict
from typing import Optional

import psycopg
from google import genai
from google.genai import types

from evaluation.schemas import EvalExample
from ingestion.processing.database import (
    get_postgres_connection_string,
    load_environment,
)


# =============================================================
# Benchmark configuration
# =============================================================

DEFAULT_DISTRIBUTION = {
    "financial_metric": 0.10,
    "table_reasoning": 0.15,
    "comparison_within_source": 0.15,
    "cross_report_comparison": 0.20,
    "calculation": 0.20,
    "multi_hop": 0.15,
    "financial_interpretation": 0.05,
}


FORBIDDEN_QUESTION_PATTERNS = [
    r"\bcolumn_\d+\b",
    r"\brow_\d+\b",
    r"\bchunk_\d+\b",
    r"\bsource_id\b",
    r"\btable_id\b",
    r"\bretrieval_documents\b",
    r"\bfield_\d+\b",
]


# =============================================================
# Prompts
# =============================================================

SINGLE_SOURCE_PROMPT = """
You are creating a difficult evaluation benchmark for a financial
analysis question-answering system operating over corporate annual
reports.

Generate ONE realistic financial-analysis question and its
reference answer from the supplied evidence.

The benchmark is intended to evaluate sophisticated RAG and
agentic financial-analysis systems.

The question should resemble something a financial analyst,
investor, equity researcher, credit analyst, auditor, or portfolio
manager might reasonably ask.

TASK TYPE
{task_type}

GENERAL REQUIREMENTS

1. The answer must be fully supported by the supplied source.

2. Focus specifically on FINANCIAL ANALYSIS.

Prefer questions concerning:
   - profitability
   - profit before tax
   - profit after tax
   - revenue
   - interest income
   - non-interest income
   - operating expenses
   - assets
   - liabilities
   - equity
   - loans
   - deposits
   - capital adequacy
   - liquidity
   - credit risk
   - impairment
   - earnings
   - margins
   - regulatory capital
   - segment performance
   - geographic performance
   - financial ratios
   - cash flows
   - shareholder returns
   - dividends
   - financial risk exposures
   - efficiency
   - balance-sheet composition
   - year-on-year performance

3. Avoid trivial questions about:
   - meeting dates
   - committee meeting frequency
   - addresses
   - generic definitions
   - product descriptions
   - event locations
   - executive names
   - administrative disclosures

unless the information is directly necessary for a meaningful
financial-analysis task.

4. Do not use external knowledge.

5. Do not mention:
   - source IDs
   - chunk IDs
   - database fields
   - parser fields
   - column_1, column_2, etc.
   - row IDs

6. Preserve:
   - currencies
   - units
   - reporting periods
   - Group versus Company distinctions
   - subsidiaries
   - geographic segments
   - business segments

7. Do not invent financial metrics.

8. If the source contains a table, reason from the semantic row and
   column labels.

9. The question must make sense without seeing the source.

10. Prefer analytical questions over direct copying.

TASK-SPECIFIC GUIDANCE

financial_metric:
Ask for a financially meaningful metric where identifying the
correct period, entity, unit, category, or statement item requires
care.

Avoid arbitrary isolated numbers that have little analytical value.

table_reasoning:
Require reasoning across at least two meaningful cells, rows,
columns, periods, entities, or financial categories.

Examples:
- Which segment generated the highest profit?
- How did Group deposits compare with Company deposits?
- How much larger was one financial category than another?

Avoid simply asking for one table cell.

comparison_within_source:
Require comparison between at least two financially meaningful
values contained in the same source.

Examples:
- Group versus Company;
- two segments;
- two geographic regions;
- current versus prior period;
- two financial statement categories.

financial_interpretation:
Require a financial conclusion directly supported by values in the
source.

Examples:
- Which segment was the stronger contributor to profitability?
- Did the capital position strengthen or weaken?
- Which category represented the greater risk exposure?

Do not speculate beyond the evidence.

Return JSON only:

{{
  "question": "...",
  "reference_answer": "...",
  "category": "{task_type}",
  "answerable": true
}}
""".strip()


MULTI_SOURCE_PROMPT = """
You are creating a difficult evaluation benchmark for an agentic
financial-analysis system operating over corporate annual reports.

Generate ONE realistic financial-analysis question that requires
information from ALL supplied sources.

TASK TYPE
{task_type}

The question should resemble a task performed by a financial
analyst, equity researcher, investor, credit analyst, auditor, or
portfolio manager.

GENERAL REQUIREMENTS

1. The question must genuinely require at least two supplied
   evidence sources.

2. Focus on meaningful FINANCIAL ANALYSIS.

Preferred topics include:
   - profitability growth
   - PBT growth
   - PAT growth
   - revenue growth
   - earnings growth
   - interest income
   - operating expenses
   - margins
   - asset growth
   - loan growth
   - deposit growth
   - equity growth
   - capital adequacy
   - liquidity
   - impairment
   - credit risk
   - cost efficiency
   - segment contribution
   - geographic contribution
   - dividends
   - balance-sheet composition
   - risk exposure
   - shareholder performance

3. The question should require reasoning, not merely concatenating
   independent facts.

4. Do not use external knowledge.

5. Do not expose:
   - source IDs
   - database structures
   - parser fields
   - chunk identifiers
   - column_1 / column_2 labels

6. Preserve:
   - currency
   - units
   - reporting period
   - Group versus Company
   - business segment
   - subsidiary
   - geography

7. Do not compare unrelated metrics simply because both contain
   numbers.

8. Do not create synthetic ratios unless the numerator and
   denominator represent financially compatible quantities.

9. Do not treat approximate quantities such as:
   - over
   - about
   - approximately
   - more than
   - less than
as exact numbers.

10. If the supplied evidence cannot support a meaningful financial
    analysis question, return answerable=false.

TASK-SPECIFIC GUIDANCE

cross_report_comparison:

Require the SAME meaningful financial metric across multiple
reporting periods.

Examples:
- How did PBT change from 2023 to 2024?
- How did total assets change year-on-year?
- Did capital adequacy strengthen or weaken?
- How did customer deposits change across periods?

The reference answer must identify the relevant values and the
direction of change.

calculation:

Require deterministic financial arithmetic.

Preferred calculations include:

Percentage growth:
(current - previous) / previous * 100

Absolute change:
current - previous

Contribution:
component / total * 100

Margin:
profit / revenue * 100

Ratio:
numerator / denominator

Percentage-point change:
current_percentage - previous_percentage

The calculation must be financially meaningful.

Do not calculate ratios between unrelated quantities.

Do not treat approximate values as exact.

The reference answer must state:
1. the input values;
2. the calculation;
3. the result;
4. a concise financial interpretation.

multi_hop:

Require combining financial evidence from at least two sources.

The answer must not be obtainable from either source independently.

Examples:
- combine statement values with segment disclosures;
- combine profitability with balance-sheet information;
- determine contribution using a metric from one source and a
  total from another;
- compare subsidiary or geographic performance across disclosures.

financial_interpretation:

Require synthesis across multiple financial evidence sources.

The answer must make an objective conclusion supported directly by
the supplied values.

Examples:
- Did profitability grow faster than the balance sheet?
- Did deposit growth keep pace with loan growth?
- Which business segment appears to have been the main contributor
  to the change in profitability?

Avoid investment recommendations and unsupported causal claims.

For calculation tasks, return a plain arithmetic expression using
numeric values only.

Return JSON only.

For non-calculation tasks:

{{
  "question": "...",
  "reference_answer": "...",
  "category": "{task_type}",
  "answerable": true,
  "calculation_expression": null
}}

For calculation tasks:

{{
  "question": "...",
  "reference_answer": "...",
  "category": "calculation",
  "answerable": true,
  "calculation_expression": "..."
}}
""".strip()


VALIDATION_PROMPT = """
You are a strict financial analyst validating a synthetic benchmark
example for a financial-analysis RAG and agent system.

The benchmark should be sufficiently challenging to differentiate
strong retrieval and reasoning systems from simple lookup systems.

Evaluate the proposed question and reference answer against the
supplied evidence.

A valid benchmark example must satisfy ALL criteria below.

FINANCIAL RELEVANCE

1. The question must concern meaningful financial analysis.

2. Reject questions primarily about:
   - meeting dates
   - event locations
   - generic corporate facts
   - executive names
   - simple definitions
   - product descriptions
   - administrative disclosures

unless directly required for a financial-analysis task.

GROUNDING

3. Every factual claim in the reference answer must be supported
   by the supplied evidence.

4. Currency, units, period, entity, subsidiary, geography,
   segment, and Group/Company distinctions must be correct.

5. The reference answer must not make a stronger claim than the
   evidence supports.

DIFFICULTY

6. The task should require at least one of:
   - careful financial metric identification;
   - table reasoning;
   - comparison;
   - arithmetic;
   - multi-source retrieval;
   - multi-hop reasoning;
   - financial interpretation.

7. Reject trivial questions where the answer is merely a
   conspicuous isolated fact unless the financial_metric category
   still requires careful identification of entity, period, unit,
   or financial statement item.

SEMANTIC VALIDITY

8. Reject invented financial metrics.

9. Reject comparisons between unrelated financial quantities.

10. For calculations:
    - all inputs must be supported by evidence;
    - approximate values cannot be treated as exact;
    - numerator and denominator must be financially compatible;
    - arithmetic must be correct;
    - the resulting metric must have meaningful financial
      interpretation.

11. For cross-report comparisons, the values must represent the
    same financial or accounting concept across periods.

12. For multi-hop questions, all supplied sources must genuinely
    contribute to the answer.

13. For table reasoning, the question must rely on semantic table
    structure rather than parser artifacts.

NATURALNESS

14. The question should resemble something a financial analyst,
    investor, credit analyst, auditor, or researcher could
    realistically ask.

15. Reject parser-oriented wording such as:
    column_2,
    row_3,
    source_id,
    chunk identifiers,
    database terminology.

QUALITY

Assign:

quality_score:
Overall quality from 0.0 to 1.0.

difficulty_score:
How strongly the question tests retrieval/reasoning rather than
simple lookup.

financial_relevance_score:
How strongly the question represents genuine financial analysis.

Suggested interpretation:

1.00
Excellent.

0.90
Strong.

0.80
Usable but relatively easy or imperfect.

Below 0.80
Not suitable for the final benchmark.

Return JSON only:

{
  "valid": true,
  "quality_score": 0.95,
  "difficulty_score": 0.90,
  "financial_relevance_score": 1.0,
  "reason": "Brief explanation.",
  "corrected_question": null,
  "corrected_reference_answer": null
}

If a minor wording issue can safely be corrected, provide the
corrected question or reference answer.

If there is a financial, semantic, calculation, or grounding
problem, set valid=false.
""".strip()


# =============================================================
# Database sampling
# =============================================================


def fetch_candidate_documents(
    pool_size: int = 2000,
) -> list[dict]:
    """
    Retrieve a stratified candidate pool across ticker and
    reporting year.

    This prevents one company or reporting period from dominating
    benchmark generation.
    """

    load_environment()

    connection_string = (
        get_postgres_connection_string()
    )

    group_query = """
        SELECT
            ticker,
            report_year,
            COUNT(*) AS document_count
        FROM financial_analysis.retrieval_documents
        WHERE text IS NOT NULL
          AND length(text) >= 120
          AND ticker IS NOT NULL
          AND report_year IS NOT NULL
        GROUP BY ticker, report_year
        ORDER BY ticker, report_year
    """

    with psycopg.connect(
        connection_string
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                group_query
            )
            groups = cursor.fetchall()

    if not groups:
        return []

    per_group = max(
        1,
        pool_size // len(groups),
    )

    sample_query = """
        SELECT
            source_id,
            content_type,
            ticker,
            report_year,
            page_start,
            page_end,
            section_title,
            text
        FROM financial_analysis.retrieval_documents
        WHERE text IS NOT NULL
          AND length(text) >= 120
          AND ticker = %s
          AND report_year = %s
        ORDER BY RANDOM()
        LIMIT %s
    """

    documents = []

    with psycopg.connect(
        connection_string
    ) as connection:
        with connection.cursor() as cursor:

            for (
                ticker,
                report_year,
                _,
            ) in groups:

                cursor.execute(
                    sample_query,
                    (
                        ticker,
                        report_year,
                        per_group,
                    ),
                )

                rows = cursor.fetchall()

                for row in rows:
                    documents.append(
                        {
                            "source_id": row[0],
                            "content_type": row[1],
                            "ticker": row[2],
                            "report_year": row[3],
                            "page_start": row[4],
                            "page_end": row[5],
                            "section_title": row[6],
                            "text": row[7],
                        }
                    )

    # Fill remaining capacity from the complete corpus.
    remaining = (
        pool_size
        - len(documents)
    )

    if remaining > 0:
        existing_ids = {
            document["source_id"]
            for document in documents
        }

        fill_query = """
            SELECT
                source_id,
                content_type,
                ticker,
                report_year,
                page_start,
                page_end,
                section_title,
                text
            FROM financial_analysis.retrieval_documents
            WHERE text IS NOT NULL
              AND length(text) >= 120
              AND ticker IS NOT NULL
              AND report_year IS NOT NULL
            ORDER BY RANDOM()
            LIMIT %s
        """

        with psycopg.connect(
            connection_string
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    fill_query,
                    (
                        max(
                            remaining * 3,
                            remaining,
                        ),
                    ),
                )

                extra_rows = cursor.fetchall()

        for row in extra_rows:

            if len(documents) >= pool_size:
                break

            source_id = row[0]

            if source_id in existing_ids:
                continue

            documents.append(
                {
                    "source_id": row[0],
                    "content_type": row[1],
                    "ticker": row[2],
                    "report_year": row[3],
                    "page_start": row[4],
                    "page_end": row[5],
                    "section_title": row[6],
                    "text": row[7],
                }
            )

            existing_ids.add(
                source_id
            )

    return documents[:pool_size]


# =============================================================
# Source formatting
# =============================================================


def _format_document(
    document: dict,
    number: Optional[int] = None,
) -> str:

    prefix = (
        f"SOURCE {number}\n"
        if number is not None
        else ""
    )

    return f"""
{prefix}
Company: {document.get("ticker")}
Report year: {document.get("report_year")}
Content type: {document.get("content_type")}
Pages: {document.get("page_start")}-{document.get("page_end")}
Section: {document.get("section_title")}

CONTENT
{document.get("text")}
""".strip()


# =============================================================
# Static quality checks
# =============================================================


def _contains_forbidden_artifact(
    question: str,
) -> bool:

    question_lower = (
        question.lower()
    )

    for pattern in (
        FORBIDDEN_QUESTION_PATTERNS
    ):
        if re.search(
            pattern,
            question_lower,
        ):
            return True

    return False


def _basic_quality_check(
    question: str,
    answer: str,
) -> tuple[bool, str]:

    question = question.strip()
    answer = answer.strip()

    if not question:
        return False, "Empty question."

    if not answer:
        return False, "Empty answer."

    if len(question) < 20:
        return (
            False,
            "Question is too short.",
        )

    if len(question) > 600:
        return (
            False,
            "Question is too long.",
        )

    if len(answer) > 3000:
        return (
            False,
            "Reference answer is too long.",
        )

    if _contains_forbidden_artifact(
        question
    ):
        return (
            False,
            "Question contains extraction artifacts.",
        )

    suspicious_phrases = [
        "reported in column",
        "in column_",
        "from the provided source",
        "according to source 1",
        "according to source 2",
        "in this chunk",
        "in this table row",
    ]

    lower = question.lower()

    for phrase in suspicious_phrases:
        if phrase in lower:
            return (
                False,
                f"Suspicious wording: {phrase}",
            )

    return True, ""


# =============================================================
# Gemini helpers
# =============================================================


def _generate_json(
    client: genai.Client,
    *,
    model: str,
    prompt: str,
    temperature: float,
) -> dict:

    response = (
        client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type=(
                    "application/json"
                ),
                temperature=temperature,
            ),
        )
    )

    if not response.text:
        raise RuntimeError(
            "Gemini returned no JSON response."
        )

    try:
        return json.loads(
            response.text
        )

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Gemini returned invalid JSON."
        ) from exc


# =============================================================
# LLM validation
# =============================================================


def validate_generated_example(
    client: genai.Client,
    *,
    model: str,
    question: str,
    reference_answer: str,
    documents: list[dict],
    category: str,
    calculation_expression: Optional[str] = None,
) -> dict:

    evidence = "\n\n".join(
        _format_document(
            document,
            number=index,
        )
        for index, document
        in enumerate(
            documents,
            start=1,
        )
    )

    prompt = f"""
{VALIDATION_PROMPT}

CATEGORY
========
{category}

QUESTION
========
{question}

REFERENCE ANSWER
================
{reference_answer}

CALCULATION EXPRESSION
======================
{calculation_expression}

EVIDENCE
========
{evidence}
""".strip()

    return _generate_json(
        client,
        model=model,
        prompt=prompt,
        temperature=0.0,
    )


def _validation_scores(
    validation: dict,
) -> tuple[
    float,
    float,
    float,
]:
    """
    Extract benchmark validation scores.
    """

    quality = float(
        validation.get(
            "quality_score",
            0.0,
        )
    )

    difficulty = float(
        validation.get(
            "difficulty_score",
            0.0,
        )
    )

    financial_relevance = float(
        validation.get(
            "financial_relevance_score",
            0.0,
        )
    )

    return (
        quality,
        difficulty,
        financial_relevance,
    )


def _passes_validation_thresholds(
    *,
    quality: float,
    difficulty: float,
    financial_relevance: float,
    minimum_quality: float,
    minimum_difficulty: float,
    minimum_financial_relevance: float,
) -> bool:

    return (
        quality >= minimum_quality
        and difficulty
        >= minimum_difficulty
        and financial_relevance
        >= minimum_financial_relevance
    )


# =============================================================
# Single-source generation
# =============================================================


def generate_single_source_example(
    client: genai.Client,
    document: dict,
    *,
    category: str,
    generation_model: str,
    validation_model: str,
    minimum_quality: float,
    minimum_difficulty: float,
    minimum_financial_relevance: float,
) -> Optional[EvalExample]:

    prompt = (
        SINGLE_SOURCE_PROMPT.format(
            task_type=category
        )
        + "\n\n"
        + _format_document(
            document
        )
    )

    generated = _generate_json(
        client,
        model=generation_model,
        prompt=prompt,
        temperature=0.25,
    )

    if not generated.get(
        "answerable",
        True,
    ):
        return None

    question = str(
        generated.get(
            "question",
            "",
        )
    ).strip()

    answer = str(
        generated.get(
            "reference_answer",
            "",
        )
    ).strip()

    passed, _ = (
        _basic_quality_check(
            question,
            answer,
        )
    )

    if not passed:
        return None

    validation = (
        validate_generated_example(
            client,
            model=validation_model,
            question=question,
            reference_answer=answer,
            documents=[
                document
            ],
            category=category,
        )
    )

    if not validation.get(
        "valid",
        False,
    ):
        return None

    (
        quality_score,
        difficulty_score,
        financial_relevance_score,
    ) = _validation_scores(
        validation
    )

    if not _passes_validation_thresholds(
        quality=quality_score,
        difficulty=difficulty_score,
        financial_relevance=(
            financial_relevance_score
        ),
        minimum_quality=(
            minimum_quality
        ),
        minimum_difficulty=(
            minimum_difficulty
        ),
        minimum_financial_relevance=(
            minimum_financial_relevance
        ),
    ):
        return None

    corrected_question = (
        validation.get(
            "corrected_question"
        )
    )

    corrected_answer = (
        validation.get(
            "corrected_reference_answer"
        )
    )

    if corrected_question:
        question = str(
            corrected_question
        ).strip()

    if corrected_answer:
        answer = str(
            corrected_answer
        ).strip()

    passed, _ = (
        _basic_quality_check(
            question,
            answer,
        )
    )

    if not passed:
        return None

    expected_tools = []

    if (
        document.get(
            "content_type"
        )
        == "table"
    ):
        expected_tools.append(
            "get_table"
        )

    return EvalExample(
        id=str(
            uuid.uuid4()
        ),
        question=question,
        reference_answer=answer,
        gold_source_ids=[
            document[
                "source_id"
            ]
        ],
        ticker=document.get(
            "ticker"
        ),
        report_year=document.get(
            "report_year"
        ),
        category=category,
        expected_tools=(
            expected_tools
        ),
        metadata={
            "content_type": (
                document.get(
                    "content_type"
                )
            ),
            "page_start": (
                document.get(
                    "page_start"
                )
            ),
            "page_end": (
                document.get(
                    "page_end"
                )
            ),
            "section_title": (
                document.get(
                    "section_title"
                )
            ),
            "synthetic": True,
            "human_verified": False,
            "quality_score": (
                quality_score
            ),
            "difficulty_score": (
                difficulty_score
            ),
            "financial_relevance_score": (
                financial_relevance_score
            ),
            "validation_reason": (
                validation.get(
                    "reason"
                )
            ),
            "source_count": 1,
        },
    )


# =============================================================
# Multi-source generation
# =============================================================


def generate_multi_source_example(
    client: genai.Client,
    documents: list[dict],
    *,
    category: str,
    generation_model: str,
    validation_model: str,
    minimum_quality: float,
    minimum_difficulty: float,
    minimum_financial_relevance: float,
) -> Optional[EvalExample]:

    if len(documents) < 2:
        return None

    evidence = "\n\n".join(
        _format_document(
            document,
            number=index,
        )
        for index, document
        in enumerate(
            documents,
            start=1,
        )
    )

    prompt = (
        MULTI_SOURCE_PROMPT.format(
            task_type=category
        )
        + "\n\n"
        + evidence
    )

    generated = _generate_json(
        client,
        model=generation_model,
        prompt=prompt,
        temperature=0.25,
    )

    if not generated.get(
        "answerable",
        True,
    ):
        return None

    question = str(
        generated.get(
            "question",
            "",
        )
    ).strip()

    answer = str(
        generated.get(
            "reference_answer",
            "",
        )
    ).strip()

    calculation_expression = (
        generated.get(
            "calculation_expression"
        )
    )

    passed, _ = (
        _basic_quality_check(
            question,
            answer,
        )
    )

    if not passed:
        return None

    validation = (
        validate_generated_example(
            client,
            model=validation_model,
            question=question,
            reference_answer=answer,
            documents=documents,
            category=category,
            calculation_expression=(
                calculation_expression
            ),
        )
    )

    if not validation.get(
        "valid",
        False,
    ):
        return None

    (
        quality_score,
        difficulty_score,
        financial_relevance_score,
    ) = _validation_scores(
        validation
    )

    if not _passes_validation_thresholds(
        quality=quality_score,
        difficulty=difficulty_score,
        financial_relevance=(
            financial_relevance_score
        ),
        minimum_quality=(
            minimum_quality
        ),
        minimum_difficulty=(
            minimum_difficulty
        ),
        minimum_financial_relevance=(
            minimum_financial_relevance
        ),
    ):
        return None

    corrected_question = (
        validation.get(
            "corrected_question"
        )
    )

    corrected_answer = (
        validation.get(
            "corrected_reference_answer"
        )
    )

    if corrected_question:
        question = str(
            corrected_question
        ).strip()

    if corrected_answer:
        answer = str(
            corrected_answer
        ).strip()

    passed, _ = (
        _basic_quality_check(
            question,
            answer,
        )
    )

    if not passed:
        return None

    expected_tools = [
        "search_hybrid"
    ]

    if any(
        document.get(
            "content_type"
        )
        == "table"
        for document
        in documents
    ):
        expected_tools.append(
            "get_table"
        )

    if category == "calculation":
        expected_tools.append(
            "calculate"
        )

    expected_tools = list(
        dict.fromkeys(
            expected_tools
        )
    )

    ticker_values = {
        document.get(
            "ticker"
        )
        for document in documents
        if document.get(
            "ticker"
        )
    }

    year_values = {
        document.get(
            "report_year"
        )
        for document in documents
        if document.get(
            "report_year"
        )
        is not None
    }

    ticker = (
        next(
            iter(
                ticker_values
            )
        )
        if len(
            ticker_values
        )
        == 1
        else None
    )

    report_year = (
        next(
            iter(
                year_values
            )
        )
        if len(
            year_values
        )
        == 1
        else None
    )

    metadata = {
        "synthetic": True,
        "human_verified": False,
        "quality_score": (
            quality_score
        ),
        "difficulty_score": (
            difficulty_score
        ),
        "financial_relevance_score": (
            financial_relevance_score
        ),
        "validation_reason": (
            validation.get(
                "reason"
            )
        ),
        "source_count": (
            len(
                documents
            )
        ),
        "source_content_types": [
            document.get(
                "content_type"
            )
            for document
            in documents
        ],
        "source_pages": [
            {
                "page_start": (
                    document.get(
                        "page_start"
                    )
                ),
                "page_end": (
                    document.get(
                        "page_end"
                    )
                ),
            }
            for document
            in documents
        ],
    }

    if calculation_expression:
        metadata[
            "calculation_expression"
        ] = (
            calculation_expression
        )

    return EvalExample(
        id=str(
            uuid.uuid4()
        ),
        question=question,
        reference_answer=answer,
        gold_source_ids=[
            document[
                "source_id"
            ]
            for document
            in documents
        ],
        ticker=ticker,
        report_year=report_year,
        category=category,
        expected_tools=(
            expected_tools
        ),
        metadata=metadata,
    )


# =============================================================
# Source grouping
# =============================================================


def _group_by_ticker_and_year(
    documents: list[dict],
) -> dict:

    grouped = defaultdict(
        list
    )

    for document in documents:
        key = (
            document.get(
                "ticker"
            ),
            document.get(
                "report_year"
            ),
        )

        grouped[
            key
        ].append(
            document
        )

    return grouped


def _normalize_section(
    value: Optional[str],
) -> str:

    if not value:
        return ""

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        value.lower(),
    ).strip()


def _financial_similarity_score(
    first: dict,
    second: dict,
) -> int:
    """
    Basic heuristic for selecting plausible source pairs.
    """

    score = 0

    if (
        first.get(
            "content_type"
        )
        == second.get(
            "content_type"
        )
    ):
        score += 1

    first_section = (
        _normalize_section(
            first.get(
                "section_title"
            )
        )
    )

    second_section = (
        _normalize_section(
            second.get(
                "section_title"
            )
        )
    )

    if (
        first_section
        and second_section
        and first_section
        == second_section
    ):
        score += 3

    financial_terms = [
        "profit",
        "income",
        "revenue",
        "asset",
        "liability",
        "equity",
        "loan",
        "deposit",
        "capital",
        "liquidity",
        "impairment",
        "risk",
        "dividend",
        "cash flow",
        "segment",
    ]

    first_text = (
        (
            first.get(
                "section_title"
            )
            or ""
        )
        + " "
        + (
            first.get(
                "text"
            )
            or ""
        )[:1000]
    ).lower()

    second_text = (
        (
            second.get(
                "section_title"
            )
            or ""
        )
        + " "
        + (
            second.get(
                "text"
            )
            or ""
        )[:1000]
    ).lower()

    for term in financial_terms:

        if (
            term in first_text
            and term in second_text
        ):
            score += 1

    return score


def _build_cross_year_pairs(
    documents: list[dict],
) -> list[list[dict]]:
    """
    Generate same-company, different-year candidate pairs with
    financial-semantic compatibility.
    """

    by_ticker = defaultdict(
        lambda: defaultdict(
            list
        )
    )

    for document in documents:

        ticker = document.get(
            "ticker"
        )

        year = document.get(
            "report_year"
        )

        if (
            ticker is None
            or year is None
        ):
            continue

        by_ticker[
            ticker
        ][
            year
        ].append(
            document
        )

    candidate_pairs = []

    for _, years in (
        by_ticker.items()
    ):

        year_list = sorted(
            years.keys()
        )

        for first_index in range(
            len(
                year_list
            )
        ):

            for second_index in range(
                first_index + 1,
                len(
                    year_list
                ),
            ):

                first_year = (
                    year_list[
                        first_index
                    ]
                )

                second_year = (
                    year_list[
                        second_index
                    ]
                )

                for first_doc in (
                    years[
                        first_year
                    ][
                        :120
                    ]
                ):

                    scored_candidates = []

                    for second_doc in (
                        years[
                            second_year
                        ][
                            :120
                        ]
                    ):

                        score = (
                            _financial_similarity_score(
                                first_doc,
                                second_doc,
                            )
                        )

                        if score >= 2:
                            scored_candidates.append(
                                (
                                    score,
                                    second_doc,
                                )
                            )

                    scored_candidates.sort(
                        key=lambda item: (
                            item[0]
                        ),
                        reverse=True,
                    )

                    for _, second_doc in (
                        scored_candidates[:5]
                    ):
                        candidate_pairs.append(
                            [
                                first_doc,
                                second_doc,
                            ]
                        )

    return candidate_pairs


def _build_same_report_pairs(
    documents: list[dict],
) -> list[list[dict]]:
    """
    Build financially compatible multi-source pairs within the
    same ticker/report year.
    """

    grouped = (
        _group_by_ticker_and_year(
            documents
        )
    )

    pairs = []

    for group_documents in (
        grouped.values()
    ):

        for first_index in range(
            len(
                group_documents
            )
        ):

            first = (
                group_documents[
                    first_index
                ]
            )

            scored_candidates = []

            for second_index in range(
                first_index + 1,
                len(
                    group_documents
                ),
            ):

                second = (
                    group_documents[
                        second_index
                    ]
                )

                score = (
                    _financial_similarity_score(
                        first,
                        second,
                    )
                )

                if score >= 1:
                    scored_candidates.append(
                        (
                            score,
                            second,
                        )
                    )

            scored_candidates.sort(
                key=lambda item: (
                    item[0]
                ),
                reverse=True,
            )

            for _, second in (
                scored_candidates[:4]
            ):
                pairs.append(
                    [
                        first,
                        second,
                    ]
                )

    return pairs


# =============================================================
# Benchmark distribution
# =============================================================


def _target_counts(
    n: int,
    distribution: dict[
        str,
        float,
    ],
) -> dict[str, int]:

    total_weight = sum(
        distribution.values()
    )

    if total_weight <= 0:
        raise ValueError(
            "Benchmark distribution must have positive weight."
        )

    normalized = {
        category: (
            proportion
            / total_weight
        )
        for category, proportion
        in distribution.items()
    }

    counts = {
        category: int(
            round(
                n * proportion
            )
        )
        for category, proportion
        in normalized.items()
    }

    difference = (
        n
        - sum(
            counts.values()
        )
    )

    categories = list(
        counts.keys()
    )

    index = 0

    while difference != 0:

        category = (
            categories[
                index
                % len(
                    categories
                )
            ]
        )

        if difference > 0:
            counts[
                category
            ] += 1
            difference -= 1

        elif (
            counts[
                category
            ]
            > 0
        ):
            counts[
                category
            ] -= 1
            difference += 1

        index += 1

    return counts


def _normalize_question(
    question: str,
) -> str:

    return re.sub(
        r"\s+",
        " ",
        question.lower(),
    ).strip()


# =============================================================
# Distribution reporting
# =============================================================


def _print_candidate_distribution(
    documents: list[dict],
) -> None:

    distribution = (
        defaultdict(
            int
        )
    )

    for document in documents:

        distribution[
            (
                document.get(
                    "ticker"
                ),
                document.get(
                    "report_year"
                ),
            )
        ] += 1

    print()
    print(
        "=" * 80
    )
    print(
        "CANDIDATE POOL DISTRIBUTION"
    )
    print(
        "=" * 80
    )

    for (
        ticker,
        report_year,
    ), count in sorted(
        distribution.items(),
        key=lambda item: (
            str(
                item[0][0]
            ),
            str(
                item[0][1]
            ),
        ),
    ):
        print(
            f"{ticker} "
            f"{report_year}: "
            f"{count}"
        )


def _print_final_distribution(
    examples: list[
        EvalExample
    ],
) -> None:

    distribution = (
        defaultdict(
            int
        )
    )

    for example in examples:

        distribution[
            (
                example.ticker,
                example.report_year,
            )
        ] += 1

    print()
    print(
        "=" * 80
    )
    print(
        "FINAL COMPANY/YEAR DISTRIBUTION"
    )
    print(
        "=" * 80
    )

    for (
        ticker,
        report_year,
    ), count in sorted(
        distribution.items(),
        key=lambda item: (
            str(
                item[0][0]
            ),
            str(
                item[0][1]
            ),
        ),
    ):
        print(
            f"{ticker} "
            f"{report_year}: "
            f"{count}"
        )


# =============================================================
# Main benchmark generation
# =============================================================


def generate_dataset(
    *,
    n: int,
    model: str,
    seed: int = 42,
    pool_size: int = 2000,
    validation_model: Optional[str] = None,
    minimum_quality: float = 0.90,
    minimum_difficulty: float = 0.80,
    minimum_financial_relevance: float = 0.90,
    max_attempt_multiplier: int = 10,
    distribution: Optional[
        dict[str, float]
    ] = None,
) -> list[EvalExample]:

    load_environment()

    if n <= 0:
        raise ValueError(
            "n must be greater than 0."
        )

    if validation_model is None:
        validation_model = (
            model
        )

    if distribution is None:
        distribution = (
            DEFAULT_DISTRIBUTION
        )

    rng = random.Random(
        seed
    )

    documents = (
        fetch_candidate_documents(
            pool_size=pool_size
        )
    )

    if not documents:
        raise RuntimeError(
            "No candidate retrieval documents were found."
        )

    _print_candidate_distribution(
        documents
    )

    table_docs = [
        document
        for document in documents
        if document.get(
            "content_type"
        )
        == "table"
    ]

    cross_year_pairs = (
        _build_cross_year_pairs(
            documents
        )
    )

    same_report_pairs = (
        _build_same_report_pairs(
            documents
        )
    )

    rng.shuffle(
        documents
    )

    rng.shuffle(
        table_docs
    )

    rng.shuffle(
        cross_year_pairs
    )

    rng.shuffle(
        same_report_pairs
    )

    client = (
        genai.Client()
    )

    targets = (
        _target_counts(
            n,
            distribution,
        )
    )

    generated_examples = []

    existing_questions = set()

    generated_by_category = (
        defaultdict(
            int
        )
    )

    attempts_by_category = (
        defaultdict(
            int
        )
    )

    print()
    print(
        "=" * 80
    )
    print(
        "BENCHMARK TARGET DISTRIBUTION"
    )
    print(
        "=" * 80
    )

    for category, count in (
        targets.items()
    ):
        print(
            f"{category}: {count}"
        )

    for category, target in (
        targets.items()
    ):

        print()
        print(
            "=" * 80
        )
        print(
            f"Generating {category}"
        )
        print(
            f"Target: {target}"
        )
        print(
            "=" * 80
        )

        maximum_attempts = max(
            target
            * max_attempt_multiplier,
            30,
        )

        while (
            generated_by_category[
                category
            ]
            < target
            and attempts_by_category[
                category
            ]
            < maximum_attempts
        ):

            attempts_by_category[
                category
            ] += 1

            example = None

            try:

                # =================================================
                # Financial metric
                # =================================================

                if (
                    category
                    == "financial_metric"
                ):

                    document = (
                        rng.choice(
                            documents
                        )
                    )

                    example = (
                        generate_single_source_example(
                            client,
                            document,
                            category=category,
                            generation_model=model,
                            validation_model=(
                                validation_model
                            ),
                            minimum_quality=(
                                minimum_quality
                            ),
                            minimum_difficulty=(
                                minimum_difficulty
                            ),
                            minimum_financial_relevance=(
                                minimum_financial_relevance
                            ),
                        )
                    )

                # =================================================
                # Table reasoning
                # =================================================

                elif (
                    category
                    == "table_reasoning"
                ):

                    if not table_docs:
                        break

                    document = (
                        rng.choice(
                            table_docs
                        )
                    )

                    example = (
                        generate_single_source_example(
                            client,
                            document,
                            category=category,
                            generation_model=model,
                            validation_model=(
                                validation_model
                            ),
                            minimum_quality=(
                                minimum_quality
                            ),
                            minimum_difficulty=(
                                minimum_difficulty
                            ),
                            minimum_financial_relevance=(
                                minimum_financial_relevance
                            ),
                        )
                    )

                # =================================================
                # Same-source comparison
                # =================================================

                elif (
                    category
                    == "comparison_within_source"
                ):

                    document = (
                        rng.choice(
                            documents
                        )
                    )

                    example = (
                        generate_single_source_example(
                            client,
                            document,
                            category=category,
                            generation_model=model,
                            validation_model=(
                                validation_model
                            ),
                            minimum_quality=(
                                minimum_quality
                            ),
                            minimum_difficulty=(
                                minimum_difficulty
                            ),
                            minimum_financial_relevance=(
                                minimum_financial_relevance
                            ),
                        )
                    )

                # =================================================
                # Single-source interpretation
                # =================================================

                elif (
                    category
                    == "financial_interpretation"
                ):

                    document = (
                        rng.choice(
                            documents
                        )
                    )

                    example = (
                        generate_single_source_example(
                            client,
                            document,
                            category=category,
                            generation_model=model,
                            validation_model=(
                                validation_model
                            ),
                            minimum_quality=(
                                minimum_quality
                            ),
                            minimum_difficulty=(
                                minimum_difficulty
                            ),
                            minimum_financial_relevance=(
                                minimum_financial_relevance
                            ),
                        )
                    )

                # =================================================
                # Cross-report comparison
                # =================================================

                elif (
                    category
                    == "cross_report_comparison"
                ):

                    if not cross_year_pairs:
                        break

                    pair = (
                        rng.choice(
                            cross_year_pairs
                        )
                    )

                    example = (
                        generate_multi_source_example(
                            client,
                            pair,
                            category=category,
                            generation_model=model,
                            validation_model=(
                                validation_model
                            ),
                            minimum_quality=(
                                minimum_quality
                            ),
                            minimum_difficulty=(
                                minimum_difficulty
                            ),
                            minimum_financial_relevance=(
                                minimum_financial_relevance
                            ),
                        )
                    )

                # =================================================
                # Calculation
                # =================================================

                elif (
                    category
                    == "calculation"
                ):

                    candidate_pairs = (
                        cross_year_pairs
                        + same_report_pairs
                    )

                    if not candidate_pairs:
                        break

                    pair = (
                        rng.choice(
                            candidate_pairs
                        )
                    )

                    example = (
                        generate_multi_source_example(
                            client,
                            pair,
                            category=category,
                            generation_model=model,
                            validation_model=(
                                validation_model
                            ),
                            minimum_quality=(
                                minimum_quality
                            ),
                            minimum_difficulty=(
                                minimum_difficulty
                            ),
                            minimum_financial_relevance=(
                                minimum_financial_relevance
                            ),
                        )
                    )

                # =================================================
                # Multi-hop
                # =================================================

                elif (
                    category
                    == "multi_hop"
                ):

                    candidate_pairs = (
                        same_report_pairs
                        + cross_year_pairs
                    )

                    if not candidate_pairs:
                        break

                    pair = (
                        rng.choice(
                            candidate_pairs
                        )
                    )

                    example = (
                        generate_multi_source_example(
                            client,
                            pair,
                            category=category,
                            generation_model=model,
                            validation_model=(
                                validation_model
                            ),
                            minimum_quality=(
                                minimum_quality
                            ),
                            minimum_difficulty=(
                                minimum_difficulty
                            ),
                            minimum_financial_relevance=(
                                minimum_financial_relevance
                            ),
                        )
                    )

                else:
                    raise ValueError(
                        "Unsupported benchmark category: "
                        f"{category}"
                    )

            except Exception as exc:

                print(
                    "Generation attempt failed: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

                continue

            if example is None:
                continue

            normalized_question = (
                _normalize_question(
                    example.question
                )
            )

            if (
                normalized_question
                in existing_questions
            ):
                continue

            existing_questions.add(
                normalized_question
            )

            generated_examples.append(
                example
            )

            generated_by_category[
                category
            ] += 1

            print(
                "["
                f"{generated_by_category[category]}"
                "/"
                f"{target}"
                "] "
                f"{example.question}"
            )

        if (
            generated_by_category[
                category
            ]
            < target
        ):
            print()
            print(
                "WARNING: Generated only "
                f"{generated_by_category[category]}"
                f"/{target} valid examples "
                f"for '{category}'."
            )

    rng.shuffle(
        generated_examples
    )

    print()
    print(
        "=" * 80
    )
    print(
        "BENCHMARK GENERATION COMPLETE"
    )
    print(
        "=" * 80
    )

    print(
        f"Requested: {n}"
    )

    print(
        "Generated: "
        f"{len(generated_examples)}"
    )

    print()
    print(
        "CATEGORY DISTRIBUTION"
    )

    for category in targets:
        print(
            f"{category}: "
            f"{generated_by_category[category]}"
        )

    print()
    print(
        "GENERATION ATTEMPTS"
    )

    for category in targets:
        print(
            f"{category}: "
            f"{attempts_by_category[category]}"
        )

    _print_final_distribution(
        generated_examples
    )

    return generated_examples
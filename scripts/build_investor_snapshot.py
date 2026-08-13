from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# =============================================================
# Paths
# =============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

SOURCE_PATH = (
    PROJECT_ROOT
    / "data"
    / "frontend"
    / "investor_metrics_source.json"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "frontend"
    / "investor_metrics.json"
)


# =============================================================
# Formatting
# =============================================================


def format_value(
    value: float,
    unit: str,
) -> str:
    """
    Convert normalized values into compact
    investor-facing strings.
    """

    if unit == "ngn_billion":

        if abs(value) >= 1000:

            return (
                f"₦{value / 1000:,.2f}tn"
            )

        return (
            f"₦{value:,.1f}bn"
        )

    if unit == "ngn_per_share":

        return (
            f"₦{value:,.2f}"
        )

    if unit == "percent":

        return (
            f"{value:,.1f}%"
        )

    return (
        f"{value:,.2f}"
    )


# =============================================================
# Growth calculation
# =============================================================


def calculate_growth(
    current: float,
    previous: float,
) -> float | None:
    """
    Calculate ordinary year-on-year percentage change.

    This should only be used where the previous
    value provides a meaningful percentage base.
    """

    if previous == 0:

        return None

    return (
        (
            current
            - previous
        )
        / abs(previous)
        * 100
    )


def format_percentage_growth(
    growth: float | None,
) -> str:
    """
    Format percentage growth for the UI.
    """

    if growth is None:

        return "N/A"

    return (
        f"{growth:+.1f}%"
    )


def build_growth_display(
    *,
    current: float,
    previous: float,
    change_mode: str,
) -> tuple[
    float | None,
    str,
]:
    """
    Determine how a change should be presented.

    A loss-to-profit transition is labelled as a
    turnaround rather than displayed as a conventional
    percentage growth rate.
    """

    if (
        change_mode == "turnaround"
        and previous < 0
        and current > 0
    ):

        return (
            None,
            "Turnaround to profit",
        )

    growth = calculate_growth(
        current=current,
        previous=previous,
    )

    return (
        growth,
        format_percentage_growth(
            growth
        ),
    )


# =============================================================
# Snapshot generation
# =============================================================


def build_snapshot() -> dict[str, Any]:
    """
    Generate the precomputed investor comparison.

    Streamlit consumes the generated JSON directly,
    avoiding database, retrieval, and LLM work at
    page load.
    """

    with SOURCE_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:

        source = json.load(
            file
        )

    output: dict[str, Any] = {
        "title": source.get(
            "title",
            "Growth Comparison",
        ),

        "subtitle": source.get(
            "subtitle",
            "",
        ),

        "as_of_year": source[
            "as_of_year"
        ],

        "previous_year": source[
            "previous_year"
        ],

        "companies": {},
    }

    for (
        ticker,
        company,
    ) in source[
        "companies"
    ].items():

        processed_metrics = []

        for metric in company[
            "metrics"
        ]:

            current = float(
                metric[
                    "current"
                ]
            )

            previous = float(
                metric[
                    "previous"
                ]
            )

            unit = str(
                metric[
                    "unit"
                ]
            )

            change_mode = str(
                metric.get(
                    "change_mode",
                    "percentage",
                )
            )

            (
                growth_percent,
                growth_display,
            ) = build_growth_display(
                current=current,
                previous=previous,
                change_mode=change_mode,
            )

            processed_metrics.append(
                {
                    **metric,

                    "display_value":
                        format_value(
                            current,
                            unit,
                        ),

                    "previous_display_value":
                        format_value(
                            previous,
                            unit,
                        ),

                    "growth_percent":
                        growth_percent,

                    "growth_display":
                        growth_display,
                }
            )

        output[
            "companies"
        ][ticker] = {
            "name": company[
                "name"
            ],

            "metrics":
                processed_metrics,
        }

    return output


# =============================================================
# Main
# =============================================================


def main() -> None:
    """
    Write the precomputed snapshot to disk.
    """

    snapshot = (
        build_snapshot()
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            snapshot,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        (
            "Investor growth comparison "
            f"written to {OUTPUT_PATH}"
        )
    )


if __name__ == "__main__":
    main()
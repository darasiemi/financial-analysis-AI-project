from __future__ import annotations

from typing import Any


def build_context(
    results: list[dict[str, Any]],
) -> str:
    """
    Convert retrieved documents into context for the LLM.
    """

    blocks: list[str] = []

    for index, result in enumerate(
        results,
        start=1,
    ):
        lines = [
            f"[SOURCE {index}]",
            f"Type: {result['content_type']}",
            f"Ticker: {result['ticker']}",
            f"Report year: {result['report_year']}",
            (
                "Pages: "
                f"{result['page_start']}-"
                f"{result['page_end']}"
            ),
        ]

        section_title = result.get(
            "section_title"
        )

        if section_title:
            lines.append(
                f"Section: {section_title}"
            )

        lines.extend(
            [
                "",
                result["text"],
            ]
        )

        blocks.append(
            "\n".join(lines)
        )

    return "\n\n".join(blocks)
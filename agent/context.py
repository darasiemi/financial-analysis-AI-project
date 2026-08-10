from __future__ import annotations

from typing import Any


def build_initial_context(
    retrieval_result: dict[str, Any],
) -> str:
    """
    Convert initial retrieval results into readable evidence
    for the agent.

    The initial evidence comes from the local annual-report
    retrieval index before Gemini begins autonomous tool use.
    """

    documents = retrieval_result.get(
        "documents",
        [],
    )

    if not documents:
        return (
            "No relevant evidence was found in the initial "
            "annual-report retrieval."
        )

    blocks: list[str] = []

    for index, document in enumerate(
        documents,
        start=1,
    ):
        lines = [
            f"[INITIAL SOURCE {index}]",
            (
                "Content type: "
                f"{document['content_type']}"
            ),
            (
                "Source ID: "
                f"{document['source_id']}"
            ),
            (
                "Ticker: "
                f"{document['ticker']}"
            ),
            (
                "Report year: "
                f"{document['report_year']}"
            ),
            (
                "Pages: "
                f"{document['page_start']}-"
                f"{document['page_end']}"
            ),
        ]

        section_title = document.get(
            "section_title"
        )

        if section_title:
            lines.append(
                f"Section: {section_title}"
            )

        lines.extend(
            [
                "",
                document["text"],
            ]
        )

        blocks.append(
            "\n".join(lines)
        )

    return "\n\n".join(blocks)
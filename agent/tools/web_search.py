import os

from google import genai
from google.genai import types

from ingestion.processing.database import load_environment
from monitoring.telemetry import (
    record_gemini_response,
)


def _extract_sources(
    response,
) -> list[dict]:
    """
    Extract grounding sources from a Gemini response produced
    with Google Search grounding.

    Returns:
        A list like:
        [
            {
                "title": "...",
                "url": "..."
            }
        ]
    """

    sources = []

    candidates = getattr(
        response,
        "candidates",
        None,
    )

    if not candidates:
        return sources

    candidate = candidates[0]

    grounding_metadata = getattr(
        candidate,
        "grounding_metadata",
        None,
    )

    if grounding_metadata is None:
        return sources

    grounding_chunks = getattr(
        grounding_metadata,
        "grounding_chunks",
        None,
    )

    if not grounding_chunks:
        return sources

    seen_urls = set()

    for chunk in grounding_chunks:
        web = getattr(
            chunk,
            "web",
            None,
        )

        if web is None:
            continue

        url = getattr(
            web,
            "uri",
            None,
        )

        title = getattr(
            web,
            "title",
            None,
        )

        if not url:
            continue

        if url in seen_urls:
            continue

        seen_urls.add(url)

        sources.append(
            {
                "title": (title or "Web source"),
                "url": url,
            }
        )

    return sources


def web_search(
    query: str,
) -> dict:
    """
    Search the public web using Gemini with Google Search grounding.

    Use this tool when:
    - current or recent information is required;
    - the answer is newer than the available annual reports;
    - external public verification is requested;
    - information is not available in the local annual-report
      database.

    Prefer local annual-report retrieval tools when the requested
    information should come from an ingested annual report.

    Args:
        query:
            Public web search query.

    Returns:
        Grounded web answer and source metadata.
    """

    try:
        load_environment()

        api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
            return {
                "success": False,
                "query": query,
                "error_type": ("ConfigurationError"),
                "error": ("GEMINI_API_KEY is not configured."),
            }

        client = genai.Client(api_key=api_key)

        model = os.environ.get(
            "GEMINI_WEB_MODEL",
            "gemini-2.5-flash",
        )

        google_search_tool = types.Tool(google_search=types.GoogleSearch())

        response = client.models.generate_content(
            model=model,
            contents=query,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                temperature=0.1,
            ),
        )

        record_gemini_response(
            response=response,
            model=model,
            purpose="web_search",
        )

        answer = response.text or ""

        sources = _extract_sources(response)

        return {
            "success": True,
            "query": query,
            "answer": answer,
            "sources": sources,
        }

    except Exception as exc:
        return {
            "success": False,
            "query": query,
            "error_type": (type(exc).__name__),
            "error": str(exc),
        }

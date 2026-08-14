import os
import time

from google import genai
from google.genai import types

from agent.tools.retrieval import (
    search_hybrid,
    search_keyword,
    search_semantic,
)
from evaluation.schemas import (
    EvalExample,
    PipelineResult,
)

SEARCH_FUNCTIONS = {
    "keyword": search_keyword,
    "vector": search_semantic,
    "hybrid": search_hybrid,
}


class RAGAdapter:

    def __init__(
        self,
        *,
        mode: str = "hybrid",
        top_k: int = 8,
        model: str | None = None,
    ) -> None:

        if mode not in SEARCH_FUNCTIONS:
            raise ValueError(f"Unsupported retrieval mode: {mode}")

        self.mode = mode
        self.top_k = top_k

        self.model = model or os.environ.get(
            "GEMINI_RAG_MODEL",
            "gemini-2.5-flash",
        )

        self.client = genai.Client()

    def run(
        self,
        example: EvalExample,
    ) -> PipelineResult:

        start = time.perf_counter()

        search = SEARCH_FUNCTIONS[self.mode]

        retrieval = search(
            query=example.question,
            ticker=example.ticker,
            report_year=(example.report_year),
            top_k=self.top_k,
        )

        if not retrieval.get("success"):
            raise RuntimeError(
                retrieval.get(
                    "error",
                    "Retrieval failed.",
                )
            )

        documents = retrieval.get(
            "documents",
            [],
        )

        source_ids = [document["source_id"] for document in documents]

        contexts = [document["text"] for document in documents]

        context_text = "\n\n".join(
            (f"[SOURCE {index}]\n" f"{document['text']}")
            for index, document in enumerate(
                documents,
                start=1,
            )
        )

        prompt = f"""
Answer the question using only the supplied annual-report context.

If the context is insufficient, say so.

Preserve currencies, units, reporting periods, and Group/Company
distinctions.

QUESTION
{example.question}

CONTEXT
{context_text}
""".strip()

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
            ),
        )

        answer = response.text or ""

        elapsed = time.perf_counter() - start

        return PipelineResult(
            answer=answer,
            initial_retrieved_source_ids=(source_ids),
            retrieved_source_ids=(source_ids),
            contexts=contexts,
            latency_seconds=elapsed,
            metadata={
                "pipeline": "rag",
                "retrieval_mode": (self.mode),
            },
        )

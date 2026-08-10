from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class EvalExample:
    id: str
    question: str
    reference_answer: str

    gold_source_ids: list[str]

    ticker: Optional[str] = None
    report_year: Optional[int] = None

    category: str = "factual"

    # Optional manual annotation for agent evaluation.
    expected_tools: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        data: dict,
    ) -> "EvalExample":
        return cls(**data)


@dataclass
class PipelineResult:
    answer: str

    # Retrieval produced before generation/agent reasoning.
    initial_retrieved_source_ids: list[str]

    # All evidence eventually gathered.
    retrieved_source_ids: list[str]

    contexts: list[str]

    latency_seconds: float

    tool_calls: list[dict] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )
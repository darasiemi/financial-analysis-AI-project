from typing import Protocol

from evaluation.schemas import (
    EvalExample,
    PipelineResult,
)


class EvaluationAdapter(Protocol):

    def run(
        self,
        example: EvalExample,
    ) -> PipelineResult:
        ...
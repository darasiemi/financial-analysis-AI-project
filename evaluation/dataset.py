import json
from pathlib import Path

from evaluation.schemas import EvalExample


def save_dataset(
    examples: list[EvalExample],
    path: str,
) -> None:
    output_path = Path(path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        for example in examples:
            file.write(
                json.dumps(
                    example.to_dict(),
                    ensure_ascii=False,
                )
                + "\n"
            )


def load_dataset(
    path: str,
) -> list[EvalExample]:
    examples = []

    with Path(path).open(
        encoding="utf-8",
    ) as file:

        for line in file:

            line = line.strip()

            if not line:
                continue

            examples.append(
                EvalExample.from_dict(
                    json.loads(line)
                )
            )

    return examples
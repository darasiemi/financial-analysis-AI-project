import re
import string
from collections import Counter


def normalize_answer(
    text: str,
) -> str:

    text = text.lower()

    text = text.translate(
        str.maketrans(
            "",
            "",
            string.punctuation,
        )
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def token_f1(
    prediction: str,
    reference: str,
) -> float:

    predicted_tokens = normalize_answer(prediction).split()

    reference_tokens = normalize_answer(reference).split()

    if not predicted_tokens:
        return 0.0

    if not reference_tokens:
        return 0.0

    overlap = Counter(predicted_tokens) & Counter(reference_tokens)

    common = sum(overlap.values())

    if common == 0:
        return 0.0

    precision = common / len(predicted_tokens)

    recall = common / len(reference_tokens)

    return 2 * precision * recall / (precision + recall)

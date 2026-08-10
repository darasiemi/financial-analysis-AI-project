def _unwrap_response(
    response,
):
    if (
        isinstance(response, dict)
        and "result" in response
        and isinstance(
            response["result"],
            dict,
        )
    ):
        return response[
            "result"
        ]

    return response


def tool_success_rate(
    tool_calls: list[dict],
) -> float:

    if not tool_calls:
        return 1.0

    successful = 0

    for call in tool_calls:

        response = _unwrap_response(
            call.get(
                "response"
            )
        )

        if not isinstance(
            response,
            dict,
        ):
            continue

        if response.get(
            "success",
            True,
        ):
            successful += 1

    return (
        successful
        / len(tool_calls)
    )


def tool_f1(
    tool_calls: list[dict],
    expected_tools: list[str],
) -> float | None:
    """
    Optional metric.

    Only meaningful when expected_tools has been manually
    annotated.
    """

    if not expected_tools:
        return None

    predicted = {
        call.get("tool")
        for call in tool_calls
        if call.get("tool")
    }

    expected = set(
        expected_tools
    )

    true_positive = len(
        predicted
        & expected
    )

    if not predicted:
        precision = 0.0
    else:
        precision = (
            true_positive
            / len(predicted)
        )

    recall = (
        true_positive
        / len(expected)
    )

    if (
        precision
        + recall
        == 0
    ):
        return 0.0

    return (
        2
        * precision
        * recall
        / (
            precision
            + recall
        )
    )


def agent_metrics(
    tool_calls: list[dict],
    expected_tools: list[str],
) -> dict:

    metrics = {
        "tool_count": len(
            tool_calls
        ),
        "tool_success_rate": (
            tool_success_rate(
                tool_calls
            )
        ),
    }

    expected_f1 = tool_f1(
        tool_calls,
        expected_tools,
    )

    if expected_f1 is not None:
        metrics[
            "tool_f1"
        ] = expected_f1

    return metrics
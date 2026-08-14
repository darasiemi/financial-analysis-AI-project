import ast
import math
import operator

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


_ALLOWED_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "sqrt": math.sqrt,
}


def _evaluate_node(
    node: ast.AST,
):
    if isinstance(
        node,
        ast.Expression,
    ):
        return _evaluate_node(node.body)

    if isinstance(
        node,
        ast.Constant,
    ):
        if isinstance(
            node.value,
            (int, float),
        ):
            return node.value

        raise ValueError("Only numeric constants are allowed.")

    if isinstance(
        node,
        ast.BinOp,
    ):
        operator_type = type(node.op)

        if operator_type not in _BINARY_OPERATORS:
            raise ValueError("Unsupported arithmetic operator.")

        left = _evaluate_node(node.left)

        right = _evaluate_node(node.right)

        if operator_type is ast.Pow and abs(right) > 20:
            raise ValueError("Exponent is too large.")

        return _BINARY_OPERATORS[operator_type](
            left,
            right,
        )

    if isinstance(
        node,
        ast.UnaryOp,
    ):
        operator_type = type(node.op)

        if operator_type not in _UNARY_OPERATORS:
            raise ValueError("Unsupported unary operator.")

        return _UNARY_OPERATORS[operator_type](_evaluate_node(node.operand))

    if isinstance(
        node,
        ast.Call,
    ):
        if not isinstance(
            node.func,
            ast.Name,
        ):
            raise ValueError("Unsupported function call.")

        function_name = node.func.id

        if function_name not in _ALLOWED_FUNCTIONS:
            raise ValueError(f"Function '{function_name}' " "is not allowed.")

        arguments = [_evaluate_node(argument) for argument in node.args]

        return _ALLOWED_FUNCTIONS[function_name](*arguments)

    raise ValueError("Unsupported expression.")


def calculate(
    expression: str,
) -> dict:
    """
    Perform a deterministic arithmetic calculation.

    Args:
        expression:
            Arithmetic expression such as
            ((609308442 - 214154094) / 214154094) * 100

    Returns:
        Calculation result.
    """

    try:
        tree = ast.parse(
            expression,
            mode="eval",
        )

        result = _evaluate_node(tree)

        return {
            "success": True,
            "expression": expression,
            "result": result,
        }

    except (
        SyntaxError,
        TypeError,
        ValueError,
        ZeroDivisionError,
        OverflowError,
    ) as exc:
        return {
            "success": False,
            "expression": expression,
            "error_type": (type(exc).__name__),
            "error": str(exc),
        }

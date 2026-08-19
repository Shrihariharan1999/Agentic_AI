import ast
import operator

OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def evaluate(node):
    if isinstance(node, ast.Constant):
        return node.value

    elif isinstance(node, ast.BinOp):
        return OPERATORS[type(node.op)](
            evaluate(node.left),
            evaluate(node.right)
        )

    elif isinstance(node, ast.UnaryOp):
        return OPERATORS[type(node.op)](
            evaluate(node.operand)
        )

    raise ValueError("Unsupported expression")


def calculator(expression: str):
    tree = ast.parse(expression, mode="eval")
    value= evaluate(tree.body)
    print(f"Calculator tool loaded successfully. output:{value}")
    return value

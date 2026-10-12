import ast
import operator


OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def evaluate(node, depth=0):
    if depth > 30:
        raise ValueError("Aninhamento excessivo")

    if isinstance(node, ast.Expression):
        return evaluate(node.body, depth + 1)

    if isinstance(node, ast.Constant):
        if type(node.value) in (int, float):
            return node.value
        raise ValueError("Valor não numérico")

    if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
        value = evaluate(node.operand, depth + 1)
        return OPERATORS[type(node.op)](value)

    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        left = evaluate(node.left, depth + 1)
        right = evaluate(node.right, depth + 1)

        # Limita expoentes para manter os testes controlados.
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("Expoente excessivo")

        return OPERATORS[type(node.op)](left, right)

    raise ValueError("Operação não permitida")


def process_input(expression):
    tree = ast.parse(expression, mode="eval")
    result = evaluate(tree)

    # Detecta resultados numéricos não finitos.
    if isinstance(result, float):
        if result != result or abs(result) == float("inf"):
            raise ValueError("Resultado não finito")

    return result


if __name__ == "__main__":
    while True:
        expression = input("Expressão (ou 'sair'): ")

        if expression.lower() == "sair":
            break

        try:
            print("Resultado:", process_input(expression))
        except Exception as error:
            print(f"Erro: {type(error).__name__}: {error}")


import argparse
import json
import random
import string
import time
import traceback

from target import process_input


SEEDS = [
    "2 + 3",
    "10 / 2",
    "2 + 3 * 4",
    "10 / 0",
    "2 +",
    "999999999999999999 * 999999999999999999",
    "2 ** 1000",
    "((((1))))",
]

OPERATORS = ["+", "-", "*", "/", "**"]
SPECIALS = ["", "(", ")", "0", "-1", "999999", "abc", "@", "**"]


def mutate(expression):
    """Gera uma mutação tradicional de uma expressão."""

    choice = random.randint(0, 4)

    if choice == 0:
        return expression + random.choice(OPERATORS) + str(
            random.randint(0, 100)
        )

    if choice == 1:
        return random.choice(SPECIALS) + expression

    if choice == 2:
        return expression + random.choice(SPECIALS)

    if choice == 3:
        left = "(" * random.randint(1, 10)
        right = ")" * random.randint(1, 10)
        return left + expression + right

    if expression:
        position = random.randrange(len(expression))
        character = random.choice(string.punctuation + string.digits)

        return (
            expression[:position]
            + character
            + expression[position + 1:]
        )

    return expression


def generate_random_inputs(count):
    """Gera entradas com mutações aleatórias."""

    inputs = list(dict.fromkeys(SEEDS))[:count]
    seen = set(inputs)

    attempts = 0
    max_attempts = count * 100

    while len(inputs) < count and attempts < max_attempts:
        attempts += 1
        parent = random.choice(inputs)
        candidate = mutate(parent)

        if len(candidate) <= 200 and candidate not in seen:
            seen.add(candidate)
            inputs.append(candidate)

    return inputs


def run_test(expression):
    """Executa uma entrada e captura exceções."""

    started = time.perf_counter()

    try:
        result = process_input(expression)

        return {
            "input": expression,
            "status": "success",
            "result": repr(result),
            "error": None,
            "traceback": None,
            "duration_ms": round(
                (time.perf_counter() - started) * 1000, 3
            ),
        }

    except Exception as error:
        return {
            "input": expression,
            "status": "exception",
            "result": None,
            "error": f"{type(error).__name__}: {error}",
            "traceback": traceback.format_exc(),
            "duration_ms": round(
                (time.perf_counter() - started) * 1000, 3
            ),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Fuzzer tradicional e gerador assistido por Gemini."
    )

    parser.add_argument(
        "--mode",
        choices=["random", "llm"],
        default="random",
        help="Modo de geração: random ou llm.",
    )

    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Quantidade máxima de entradas a executar.",
    )

    parser.add_argument(
        "--output",
        default="results.jsonl",
        help="Arquivo JSONL de saída.",
    )

    args = parser.parse_args()

    if not 1 <= args.count <= 500:
        parser.error("--count deve estar entre 1 e 500.")

    random.seed(42)

    if args.mode == "random":
        inputs = generate_random_inputs(args.count)

    else:
        from llm_generator import generate_inputs

        # Mantém algumas sementes para permitir comparação.
        seeds = list(dict.fromkeys(SEEDS))[:args.count]
        remaining = args.count - len(seeds)

        inputs = list(seeds)

        if remaining > 0:
            print("Solicitando entradas ao Gemini...")

            try:
                generated = generate_inputs(
                    seeds,
                    count=min(remaining, 50),
                )

                seen = set(inputs)

                for expression in generated:
                    if expression not in seen:
                        inputs.append(expression)
                        seen.add(expression)

            except Exception as error:
                print(
                    "Não foi possível gerar entradas pelo Gemini: "
                    f"{type(error).__name__}: {error}"
                )
                print("Nenhum resultado da API será inventado.")

        # Caso a LLM gere menos entradas, executamos o que temos.
        inputs = inputs[:args.count]

    print(f"\nModo: {args.mode}")
    print(f"Entradas selecionadas: {len(inputs)}")

    if args.mode == "llm":
        print("Observação: as sementes também serão executadas.")

    results = []
    seen_inputs = set()
    seed_set = set(SEEDS)

    for expression in inputs:
        if expression in seen_inputs:
            continue

        seen_inputs.add(expression)
        result = run_test(expression)

        result["mode"] = args.mode
        if expression in seed_set:
            result["source"] = "seed"
        elif args.mode == "llm":
            result["source"] = "llm"
        else:
            result["source"] = "random"

        results.append(result)

        if result["status"] == "exception":
            print(
                f"[EXCEÇÃO] {expression!r} -> {result['error']}"
            )
        else:
            print(
                f"[OK] {expression!r} -> {result['result']}"
            )

    with open(args.output, "w", encoding="utf-8") as output:
        for result in results:
            output.write(
                json.dumps(result, ensure_ascii=False) + "\n"
            )

    exceptions = sum(
        item["status"] == "exception" for item in results
    )

    print("\n===== RESUMO =====")
    print(f"Modo: {args.mode}")
    print(f"Entradas executadas: {len(results)}")
    print(f"Exceções capturadas: {exceptions}")
    print(f"Execuções sem exceção: {len(results) - exceptions}")
    print(f"Arquivo de resultados: {args.output}")


if __name__ == "__main__":
    main()

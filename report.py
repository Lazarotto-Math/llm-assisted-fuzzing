
import argparse
import json
from collections import Counter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="results.jsonl",
        help="Arquivo JSONL que será analisado.",
    )
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as file:
        results = [
            json.loads(line)
            for line in file
            if line.strip()
        ]

    statuses = Counter(item["status"] for item in results)
    sources = Counter(item.get("source", "unknown") for item in results)
    errors = Counter(
        item["error"]
        for item in results
        if item.get("error")
    )

    print("===== RELATÓRIO DE FUZZING =====")
    print(f"Arquivo: {args.input}")
    print(f"Total de testes: {len(results)}")
    print(f"Sem exceção: {statuses['success']}")
    print(f"Com exceção: {statuses['exception']}")

    print("\n===== ORIGEM DAS ENTRADAS =====")
    for source, count in sources.items():
        print(f"{source}: {count}")

    print("\n===== TIPOS DE ERRO =====")
    for error, count in errors.most_common():
        print(f"{error}: {count}")


if __name__ == "__main__":
    main()

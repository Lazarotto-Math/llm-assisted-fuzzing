
import argparse
import json
from collections import Counter
from pathlib import Path


def read_jsonl(path):
    records = []
    file_path = Path(path)

    if not file_path.exists():
        print(f"Aviso: arquivo não encontrado: {path}")
        return records

    with file_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Aviso: JSON inválido em {path}, linha {line_number}")

    return records


def error_label(record):
    error = record.get("error")
    if isinstance(error, dict):
        return error.get("type", "Erro não especificado")
    if error:
        return str(error).split(":", 1)[0]
    return "Sem erro registrado"


def summarize_fuzzing(records, name):
    total = len(records)
    statuses = Counter(
        str(r.get("status", "desconhecido")).lower()
        for r in records
    )
    sources = Counter(
        str(r.get("source", "desconhecida"))
        for r in records
    )
    errors = Counter(
        error_label(r)
        for r in records
        if str(r.get("status", "")).lower()
        in {"exception", "error", "crash", "failure"}
    )

    unique_inputs = len({
        str(r.get("input", "")) for r in records
    })
    exceptions = sum(
        count for status, count in statuses.items()
        if status in {"exception", "error", "crash", "failure"}
    )
    successes = statuses.get("success", 0)

    print(f"\n=== FUZZING: {name} ===")
    print(f"Total de execuções: {total}")
    print(f"Entradas únicas: {unique_inputs}")
    print(f"Sucessos: {successes}")
    print(f"Exceções/falhas registradas: {exceptions}")
    print("Origem das entradas:")
    for source, count in sorted(sources.items()):
        print(f"  {source}: {count}")

    print("Tipos de erro mais frequentes:")
    for error, count in errors.most_common():
        print(f"  {error}: {count}")

    if total:
        print(f"Taxa de sucesso: {successes / total:.1%}")
        print(f"Taxa de exceções: {exceptions / total:.1%}")

    return {
        "name": name,
        "total": total,
        "unique": unique_inputs,
        "successes": successes,
        "exceptions": exceptions,
        "sources": sources,
        "errors": errors,
    }


def summarize_triage(records, name):
    statuses = Counter()
    failures_api = 0
    human_review = 0

    for record in records:
        triage = record.get("triage")

        if not isinstance(triage, dict):
            failures_api += 1
            continue

        statuses[triage.get("status", "Indeterminado")] += 1

        if triage.get("precisa_revisao_humana", True):
            human_review += 1

    print(f"\n=== TRIAGEM: {name} ===")
    print(f"Registros de triagem: {len(records)}")
    print(f"Análises sem resultado de classificação: {failures_api}")
    print(f"Classificações concluídas: {sum(statuses.values())}")
    print(f"Casos marcados para revisão humana: {human_review}")
    print("Classificações:")
    for status, count in statuses.most_common():
        print(f"  {status}: {count}")

    return {
        "total": len(records),
        "classified": sum(statuses.values()),
        "api_failures": failures_api,
        "statuses": statuses,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Consolida os resultados do projeto de fuzzing."
    )
    parser.add_argument(
        "--random", default="results_random.jsonl"
    )
    parser.add_argument(
        "--llm", default="results_llm.jsonl"
    )
    parser.add_argument(
        "--triage-random", default="triage_random.jsonl"
    )
    parser.add_argument(
        "--triage-llm", default="triage_llm.jsonl"
    )
    args = parser.parse_args()

    random_results = read_jsonl(args.random)
    llm_results = read_jsonl(args.llm)
    random_triage = read_jsonl(args.triage_random)
    llm_triage = read_jsonl(args.triage_llm)

    random_summary = summarize_fuzzing(random_results, "Random")
    llm_summary = summarize_fuzzing(llm_results, "LLM")

    summarize_triage(random_triage, "Random")
    summarize_triage(llm_triage, "LLM")

    print("\n=== COMPARAÇÃO ===")
    print(
        "Entradas únicas: "
        f"Random={random_summary['unique']}, "
        f"LLM={llm_summary['unique']}"
    )
    print(
        "Exceções: "
        f"Random={random_summary['exceptions']}, "
        f"LLM={llm_summary['exceptions']}"
    )
    print(
        "\nATENÇÃO: exceções não equivalem automaticamente a bugs. "
        "Compare também a quantidade de execuções, as origens das "
        "entradas e as classificações revisadas por humanos."
    )


if __name__ == "__main__":
    main()


import argparse
import json
import os
import time

from dotenv import load_dotenv
from google import genai

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL")
API_KEY = os.getenv("GEMINI_API_KEY")


def read_jsonl(path):
    """Lê os resultados do fuzzer, um objeto JSON por linha."""
    records = []

    with open(path, "r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Linha {line_number} ignorada: JSON inválido.")

    return records


def get_error(record):
    """Obtém a descrição do erro mesmo com pequenas variações no formato."""
    error = record.get("error") or record.get("exception")

    if isinstance(error, dict):
        return json.dumps(error, ensure_ascii=False)

    if error:
        return str(error)

    # Compatibilidade com registros que armazenam tipo e mensagem separados.
    error_type = record.get("exception_type", "")
    error_message = record.get("message", "")

    if error_type or error_message:
        return f"{error_type}: {error_message}".strip(": ")

    return "Erro não especificado no registro"


def parse_json_response(text):
    """Aceita JSON puro ou JSON dentro de bloco Markdown."""
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return json.loads(text)


def generate_with_retry(client, prompt, max_attempts=3):
    """Repete chamadas que falham por indisponibilidade temporária."""
    for attempt in range(max_attempts):
        try:
            return client.models.generate_content(
                model=MODEL,
                contents=prompt,
            )
        except Exception as exc:
            message = str(exc)
            temporary_error = any(
                marker in message
                for marker in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")
            )

            if not temporary_error or attempt == max_attempts - 1:
                raise

            wait_seconds = 2 ** attempt
            print(
                f"API temporariamente indisponível. "
                f"Nova tentativa em {wait_seconds}s..."
            )
            time.sleep(wait_seconds)

    raise RuntimeError("Não foi possível obter resposta da API.")



def classify_with_llm(client, record):
    expression = str(record.get("input", ""))
    error = get_error(record)
    source = record.get("source", "desconhecida")

    prompt = f"""
Você é um analista de falhas de software em um experimento de fuzzing.

O alvo é uma calculadora Python que aceita expressões aritméticas.
Ela permite +, -, *, /, ** e sinais unários + e -.
Outras operações são rejeitadas intencionalmente. Também existem
limites de profundidade e de expoente. Entradas inválidas podem
produzir exceções esperadas.

Analise o registro abaixo. Não conclua que existe um bug apenas
porque ocorreu uma exceção. Diferencie comportamento esperado
de possível defeito e não invente informações ausentes.

Entrada testada: {json.dumps(expression, ensure_ascii=False)}
Origem: {json.dumps(str(source), ensure_ascii=False)}
Erro registrado: {json.dumps(error, ensure_ascii=False)}

Responda SOMENTE com um objeto JSON válido com estas chaves:
{{
  "status": "Falso Positivo" | "Alerta" | "Crítico",
  "tipo_falha": "Sintaxe Inválida" | "Operação Não Permitida" |
                 "Erro Aritmético" | "Limite de Segurança" |
                 "Possível Falha Não Tratada" | "Indeterminado",
  "justificativa": "explicação breve baseada no registro",
  "hipotese_correcao": "correção sugerida ou 'Nenhuma necessária'",
  "confianca": "baixa" | "média" | "alta",
  "precisa_revisao_humana": true
}}

Orientações:
- "Crítico" somente com evidência de impacto grave; não presuma
  vulnerabilidade de segurança.
- "Alerta" quando houver comportamento potencialmente inesperado
  que mereça investigação.
- "Falso Positivo" para erros que parecem consequência esperada
  da validação ou de uma entrada inválida.
- Se não houver evidência suficiente, prefira "Alerta" ou
  "Indeterminado" no tipo de falha e peça revisão humana.
"""

    response = generate_with_retry(client, prompt)

    try:
        result = parse_json_response(response.text or "")
    except (json.JSONDecodeError, TypeError):
        result = {
            "status": "Alerta",
            "tipo_falha": "Indeterminado",
            "justificativa": "A resposta do modelo não veio em JSON válido.",
            "hipotese_correcao": "Revisar o registro manualmente.",
            "confianca": "baixa",
            "precisa_revisao_humana": True,
        }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Triagem de falhas do fuzzer usando Gemini."
    )
    parser.add_argument("--input", required=True, help="Arquivo JSONL do fuzzer")
    parser.add_argument("--output", required=True, help="Arquivo JSONL da triagem")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Máximo de erros analisados (0 = todos; padrão = 10)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Intervalo em segundos entre chamadas à API",
    )
    args = parser.parse_args()

    if not API_KEY:
        raise SystemExit(
            "GEMINI_API_KEY não encontrada. Confira o arquivo .env."
        )

    if not MODEL:
        raise SystemExit(
            "GEMINI_MODEL não encontrada. Confira o arquivo .env."
        )

    records = read_jsonl(args.input)

    # A triagem analisa exceções; sucessos permanecem no arquivo original.
    failures = [
        record for record in records
        if str(record.get("status", "")).lower() in {
            "exception", "error", "crash", "failure"
        }
    ]

    if args.limit > 0:
        failures = failures[:args.limit]

    print(f"Registros lidos: {len(records)}")
    print(f"Falhas selecionadas para triagem: {len(failures)}")

    client = genai.Client(api_key=API_KEY)
    completed = 0

    with open(args.output, "w", encoding="utf-8") as output_file:
        for index, record in enumerate(failures, start=1):
            try:
                triage = classify_with_llm(client, record)
                result = {
                    "input": record.get("input"),
                    "source": record.get("source", "desconhecida"),
                    "original_error": get_error(record),
                    "triage": triage,
                }
            except Exception as exc:
                # Preserva o registro mesmo se a API falhar.
                result = {
                    "input": record.get("input"),
                    "source": record.get("source", "desconhecida"),
                    "original_error": get_error(record),
                    "triage_error": f"{type(exc).__name__}: {exc}",
                }

            output_file.write(
                json.dumps(result, ensure_ascii=False) + "\n"
            )
            output_file.flush()

            completed += 1
            print(f"[{index}/{len(failures)}] Triagem registrada.")

            if index < len(failures) and args.delay > 0:
                time.sleep(args.delay)

    print(f"Concluído: {completed} registros processados.")
    print(f"Resultado salvo em: {args.output}")


if __name__ == "__main__":
    main()

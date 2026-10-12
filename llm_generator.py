
import json
import os
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
MAX_INPUT_LENGTH = 200
MAX_GENERATED_INPUTS = 50


def validate_expressions(data, limit):
    """Valida e deduplica as expressões retornadas pela LLM."""

    if not isinstance(data, dict):
        raise ValueError("A resposta deve ser um objeto JSON.")

    expressions = data.get("expressions")

    if not isinstance(expressions, list):
        raise ValueError("Campo 'expressions' ausente ou inválido.")

    valid = []
    seen = set()

    for expression in expressions:
        if not isinstance(expression, str):
            continue

        expression = expression.strip()

        if not expression or len(expression) > MAX_INPUT_LENGTH:
            continue

        # Uma expressão deve ocupar apenas uma linha.
        if "\n" in expression or "\r" in expression:
            continue

        if expression not in seen:
            seen.add(expression)
            valid.append(expression)

        if len(valid) >= limit:
            break

    return valid


def generate_inputs(seeds, count=20):
    """Solicita ao Gemini novas entradas para testar o parser."""

    if not 1 <= count <= MAX_GENERATED_INPUTS:
        raise ValueError(
            f"A quantidade deve estar entre 1 e {MAX_GENERATED_INPUTS}."
        )

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não encontrada. Verifique o arquivo .env."
        )

    client = genai.Client(api_key=api_key)

    prompt = f"""
Você é um gerador de casos de teste para um parser aritmético
implementado em Python.

O parser aceita números e os operadores +, -, *, / e **,
além de parênteses e operadores unários.

Gere exatamente {count} expressões diferentes para testar
a robustez desse parser.

Inclua uma combinação de:
- expressões válidas com diferentes precedências;
- expressões incompletas ou malformadas;
- divisão por zero;
- parênteses e operadores unários;
- números grandes;
- expoentes extremos;
- caracteres e operações não suportados.

As entradas serão executadas apenas como dados pelo parser.
Não gere código Python, comandos de sistema ou instruções
para executar código.

Sementes existentes:
{json.dumps(seeds, ensure_ascii=False)}

Retorne exclusivamente um objeto JSON neste formato:
{{
  "expressions": [
    "2 + 3",
    "10 / 0",
    "2 ** 1000"
  ]
}}

Cada item deve ser uma string. Não inclua explicações.
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.8,
            max_output_tokens=4096,
        ),
    )

    if not response.text:
        raise RuntimeError("O Gemini retornou uma resposta vazia.")

    try:
        data = json.loads(response.text)
    except json.JSONDecodeError as error:
        raise ValueError(
            "O Gemini não retornou um JSON válido."
        ) from error

    expressions = validate_expressions(data, count)

    if not expressions:
        raise ValueError(
            "Nenhuma expressão válida foi retornada pelo Gemini."
        )

    # Evita duplicar as próprias sementes.
    seed_set = set(seeds)
    return [item for item in expressions if item not in seed_set]


if __name__ == "__main__":
    test_seeds = ["2 + 3", "10 / 2", "(4 + 5) * 2"]

    try:
        results = generate_inputs(test_seeds, count=10)

        print(f"Modelo utilizado: {MODEL}")
        print(f"Entradas geradas: {len(results)}")

        for index, expression in enumerate(results, start=1):
            print(f"{index}. {expression}")

    except Exception as error:
        print(f"Falha na geração: {type(error).__name__}: {error}")

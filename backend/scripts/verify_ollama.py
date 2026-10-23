r"""Local integration-test procedure for verifying a live Ollama instance.

Requires Ollama to be running locally (`ollama serve`) with `qwen2.5:1.5b` (or a specified model) installed.
Kept separate from automated pytest unit tests so offline test runs never fail.

Usage (from backend directory in PowerShell):
    .\.venv\Scripts\python.exe -m scripts.verify_ollama
    .\.venv\Scripts\python.exe -m scripts.verify_ollama --model qwen2.5:1.5b
"""

import argparse
import asyncio
import json
import sys

from pydantic import BaseModel, Field

from app.config import OLLAMA_DEFAULT_MODEL
from app.llm.exceptions import LLMProviderError
from app.llm.ollama_provider import OllamaProvider


class StructuredPingSchema(BaseModel):
    """Pydantic schema used to verify live structured JSON generation."""

    concept: str = Field(..., min_length=2, description="Name of the scientific concept.")
    summary: str = Field(..., min_length=5, description="One-sentence plain-English explanation.")
    keywords: list[str] = Field(..., min_length=1, description="List of 2 to 4 relevant keywords.")


async def run_integration_check(model_name: str) -> int:
    provider = OllamaProvider(model_name=model_name)
    print(f"=== PaperTrail Local LLM Integration Check ({provider.provider_name} / {provider.model_name}) ===")

    # 1. Verify Ollama service and model availability
    status = await provider.check_health()
    print("\n[1/3] Service & Model Status:")
    print(json.dumps(status.model_dump(), indent=2))
    if status.status != "ready":
        print(f"\n[ERROR] Ollama is not ready: {status.message}", file=sys.stderr)
        return 1

    # 2. Verify simple text generation
    print("\n[2/3] Testing generate_text()...")
    try:
        text_res = await provider.generate_text(
            "In one concise sentence, what is a scholarly peer-reviewed paper?",
            max_tokens=80,
        )
        print(json.dumps(text_res.model_dump(), indent=2))
    except LLMProviderError as exc:
        print(f"[ERROR] generate_text() failed: {exc.message}", file=sys.stderr)
        return 1

    # 3. Verify structured JSON generation with Pydantic validation
    print("\n[3/3] Testing generate_structured() with Pydantic validation...")
    try:
        structured_res = await provider.generate_structured(
            "Describe the concept 'Citation Analysis' in academic research.",
            StructuredPingSchema,
            max_tokens=160,
        )
        print(json.dumps(structured_res.model_dump(), indent=2))
    except LLMProviderError as exc:
        print(f"[ERROR] generate_structured() failed: {exc.message}", file=sys.stderr)
        return 1

    print(f"\n[OK] All local Ollama ({provider.model_name}) integration checks passed!")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify local Ollama model integration.")
    parser.add_argument(
        "--model",
        default=OLLAMA_DEFAULT_MODEL,
        help=f"Ollama model name to test (default: {OLLAMA_DEFAULT_MODEL}).",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run_integration_check(model_name=args.model)))


if __name__ == "__main__":
    main()

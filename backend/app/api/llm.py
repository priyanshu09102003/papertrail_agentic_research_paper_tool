"""API routes for checking local LLM provider readiness."""

from functools import lru_cache

from fastapi import APIRouter, Depends

from app.config import get_gemini_api_key
from app.llm.base import BaseLLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.ollama_provider import OllamaProvider
from app.schemas import LLMStatusResponse

router = APIRouter(prefix="/api/llm", tags=["llm"])


@lru_cache(maxsize=1)
def get_llm_provider() -> BaseLLMProvider:
    """Return the default configured local LLM provider instance."""
    return OllamaProvider()


def get_extraction_llm_provider(provider_preference: str = "auto") -> BaseLLMProvider:
    """Return the LLM provider for structured scientific paper extraction.

    - 'gemini': Uses Google Gemini Flash API.
    - 'ollama': Uses local Ollama (qwen2.5:1.5b).
    - 'auto' (default): Uses Gemini Flash if GEMINI_API_KEY is configured in .env/env,
      otherwise falls back automatically to local Ollama.
    """
    pref = provider_preference.strip().lower()
    if pref == "ollama":
        return get_llm_provider()
    if pref == "gemini" or (pref == "auto" and get_gemini_api_key()):
        return GeminiProvider()
    return get_llm_provider()


@router.get(
    "/status",
    response_model=LLMStatusResponse,
    summary="Check Local LLM Status",
    description=(
        "Checks whether the local Ollama service is reachable and whether the "
        "configured default model (qwen2.5:1.5b) is installed and ready."
    ),
)
async def get_llm_status(
    provider: BaseLLMProvider = Depends(get_llm_provider),
) -> LLMStatusResponse:
    """Return safe, validated readiness status for the local LLM provider."""
    return await provider.check_health()


@router.get(
    "/extraction-status",
    response_model=LLMStatusResponse,
    summary="Check Active Scientific Extraction LLM Status",
    description=(
        "Returns the active LLM provider used for scientific paper extraction "
        "(Gemini Flash if GEMINI_API_KEY is set, otherwise local Ollama)."
    ),
)
async def get_extraction_llm_status() -> LLMStatusResponse:
    """Return readiness status for the active scientific extraction LLM provider."""
    provider = get_extraction_llm_provider("auto")
    return await provider.check_health()

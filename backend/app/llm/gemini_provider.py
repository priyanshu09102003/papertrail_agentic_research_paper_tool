"""Google Gemini REST API provider implementation for fast structured scientific extraction."""

import logging
from typing import Any

import httpx

from app.config import (
    GEMINI_API_BASE_URL,
    GEMINI_DEFAULT_MODEL,
    GEMINI_TIMEOUT_SECONDS,
    OLLAMA_CONNECT_TIMEOUT_SECONDS,
    OLLAMA_DEFAULT_TEMPERATURE,
    OLLAMA_MAX_PROMPT_CHARS,
    OLLAMA_MAX_STRUCTURED_RETRIES,
    get_gemini_api_key,
)
from app.llm.base import BaseLLMProvider
from app.llm.exceptions import (
    LLMInvalidResponseError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from app.schemas import LLMStatusResponse

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Cloud LLM provider using the Google Gemini REST API (/v1beta/models/{model}:generateContent).

    Passes the API key strictly via the 'x-goog-api-key' request header so it never
    appears in URLs or access logs.
    """

    PROVIDER_NAME = "gemini"

    FALLBACK_GENERATION_MODELS: tuple[str, ...] = (
        "gemini-3.5-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
    )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = GEMINI_API_BASE_URL,
        model_name: str = GEMINI_DEFAULT_MODEL,
        timeout_seconds: float = GEMINI_TIMEOUT_SECONDS,
        connect_timeout_seconds: float = OLLAMA_CONNECT_TIMEOUT_SECONDS,
        default_temperature: float = OLLAMA_DEFAULT_TEMPERATURE,
        max_structured_retries: int = OLLAMA_MAX_STRUCTURED_RETRIES,
        max_prompt_chars: int = OLLAMA_MAX_PROMPT_CHARS,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            provider_name=self.PROVIDER_NAME,
            model_name=model_name,
            default_temperature=default_temperature,
            max_structured_retries=max_structured_retries,
            max_prompt_chars=max_prompt_chars,
        )
        self._explicit_api_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds, connect=connect_timeout_seconds)
        self._http_client = http_client
        self._active_generation_model: str = model_name

    def _resolve_api_key(self) -> str | None:
        return self._explicit_api_key or get_gemini_api_key()

    async def check_health(self) -> LLMStatusResponse:
        """Check whether GEMINI_API_KEY is configured and the model metadata endpoint responds."""
        api_key = self._resolve_api_key()
        if not api_key:
            return LLMStatusResponse(
                provider=self.PROVIDER_NAME,
                model=self.model_name,
                service_reachable=False,
                model_available=False,
                status="unavailable",
                message="GEMINI_API_KEY is not configured. Add it to backend/.env to enable fast Gemini extraction.",
            )

        url = f"{self._base_url}/models/{self.model_name}"
        try:
            await self._request_json("GET", url, api_key=api_key)
        except LLMModelNotFoundError:
            return LLMStatusResponse(
                provider=self.PROVIDER_NAME,
                model=self.model_name,
                service_reachable=True,
                model_available=False,
                status="model_missing",
                message=f"Gemini API is reachable, but model '{self.model_name}' was not found.",
            )
        except LLMProviderError as exc:
            return LLMStatusResponse(
                provider=self.PROVIDER_NAME,
                model=self.model_name,
                service_reachable=False,
                model_available=False,
                status="unavailable",
                message=exc.message,
            )

        return LLMStatusResponse(
            provider=self.PROVIDER_NAME,
            model=self.model_name,
            service_reachable=True,
            model_available=True,
            status="ready",
            message=f"Gemini API is ready using model '{self.model_name}'.",
        )

    async def _raw_generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        """Send a POST generateContent request to the Gemini API and return the text response."""
        api_key = self._resolve_api_key()
        if not api_key:
            raise LLMServiceUnavailableError(
                "Gemini API key is not configured.",
                provider=self.PROVIDER_NAME,
            )

        generation_config: dict[str, Any] = {
            "temperature": temperature if temperature is not None else self._default_temperature,
        }
        if max_tokens is not None and max_tokens > 0:
            generation_config["maxOutputTokens"] = max(int(max_tokens), 4096) if json_mode else int(max_tokens)
        if json_mode:
            generation_config["responseMimeType"] = "application/json"

        request_body: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": generation_config,
        }
        if system_prompt and system_prompt.strip():
            request_body["systemInstruction"] = {
                "parts": [{"text": system_prompt.strip()}],
            }

        candidate_models = [self._active_generation_model]
        if self._http_client is None:
            for fallback_model in self.FALLBACK_GENERATION_MODELS:
                if fallback_model not in candidate_models:
                    candidate_models.append(fallback_model)

        payload: dict[str, Any] | None = None
        last_exc: LLMProviderError | None = None
        for candidate_model in candidate_models:
            url = f"{self._base_url}/models/{candidate_model}:generateContent"
            try:
                payload = await self._request_json("POST", url, api_key=api_key, json_body=request_body)
                self._active_generation_model = candidate_model
                break
            except (LLMModelNotFoundError, LLMTimeoutError, LLMServiceUnavailableError) as exc:
                last_exc = exc
                if "rejected or lacks permission" in exc.message or self._http_client is not None:
                    raise
                logger.info(
                    "Gemini model '%s' unavailable (%s); trying next fallback model.",
                    candidate_model,
                    exc.message,
                )
                continue

        if payload is None:
            if last_exc is not None:
                raise last_exc
            raise LLMModelNotFoundError(self.model_name, provider=self.PROVIDER_NAME)

        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise LLMInvalidResponseError(
                "The Gemini service returned no generation candidates.",
                provider=self.PROVIDER_NAME,
            )

        first_candidate = candidates[0] if isinstance(candidates[0], dict) else {}
        content = first_candidate.get("content") if isinstance(first_candidate.get("content"), dict) else {}
        parts = content.get("parts") if isinstance(content.get("parts"), list) else []
        text_fragments: list[str] = []
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                if part.get("thought") is True:
                    continue
                text_fragments.append(part["text"])

        combined_text = "".join(text_fragments).strip()
        if not combined_text:
            raise LLMInvalidResponseError(
                "The Gemini service returned an empty text response.",
                provider=self.PROVIDER_NAME,
            )
        return combined_text

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        api_key: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request against the Gemini API with safe error handling."""
        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }
        try:
            if self._http_client is not None:
                response = await self._http_client.request(
                    method, url, headers=headers, json=json_body, timeout=self._timeout
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.request(
                        method, url, headers=headers, json=json_body
                    )

            if response.status_code == 404:
                raise LLMModelNotFoundError(self.model_name, provider=self.PROVIDER_NAME)
            if response.status_code in (400, 401, 403):
                logger.warning("Gemini API authentication or request error (HTTP %d).", response.status_code)
                raise LLMServiceUnavailableError(
                    "Gemini API key was rejected or lacks permission. Check GEMINI_API_KEY in backend/.env.",
                    provider=self.PROVIDER_NAME,
                )
            if response.status_code == 429:
                raise LLMServiceUnavailableError(
                    "Gemini API rate limit reached. Please retry in a few seconds.",
                    provider=self.PROVIDER_NAME,
                )
            if response.status_code in (500, 502, 503, 504):
                raise LLMServiceUnavailableError(
                    f"Gemini API model temporarily overloaded (HTTP {response.status_code}).",
                    provider=self.PROVIDER_NAME,
                )

            response.raise_for_status()
            data = response.json()
        except LLMProviderError:
            raise
        except httpx.TimeoutException as exc:
            logger.warning("Gemini API request timed out (model=%s).", self.model_name)
            raise LLMTimeoutError(
                "The Gemini API request timed out.",
                provider=self.PROVIDER_NAME,
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.warning("Gemini API returned HTTP %d.", exc.response.status_code)
            raise LLMInvalidResponseError(
                "The Gemini API returned an unexpected HTTP status.",
                provider=self.PROVIDER_NAME,
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("Gemini API unreachable (%s).", type(exc).__name__)
            raise LLMServiceUnavailableError(
                "Unable to reach the Gemini API service.",
                provider=self.PROVIDER_NAME,
            ) from exc
        except ValueError as exc:
            raise LLMInvalidResponseError(
                "The Gemini API returned malformed JSON.",
                provider=self.PROVIDER_NAME,
            ) from exc

        if not isinstance(data, dict):
            raise LLMInvalidResponseError(
                "The Gemini API returned an unexpected JSON root structure.",
                provider=self.PROVIDER_NAME,
            )
        return data

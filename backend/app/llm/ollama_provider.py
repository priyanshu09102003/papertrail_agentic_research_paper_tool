"""Ollama local HTTP API provider implementation."""

import logging
from typing import Any

import httpx

from app.config import (
    OLLAMA_BASE_URL,
    OLLAMA_CONNECT_TIMEOUT_SECONDS,
    OLLAMA_CONTEXT_WINDOW,
    OLLAMA_DEFAULT_MODEL,
    OLLAMA_DEFAULT_TEMPERATURE,
    OLLAMA_MAX_PROMPT_CHARS,
    OLLAMA_MAX_STRUCTURED_RETRIES,
    OLLAMA_TIMEOUT_SECONDS,
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


class OllamaProvider(BaseLLMProvider):
    """Local LLM provider using the Ollama REST API (/api/generate and /api/tags)."""

    PROVIDER_NAME = "ollama"

    def __init__(
        self,
        *,
        base_url: str = OLLAMA_BASE_URL,
        model_name: str = OLLAMA_DEFAULT_MODEL,
        timeout_seconds: float = OLLAMA_TIMEOUT_SECONDS,
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
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds, connect=connect_timeout_seconds)
        self._http_client = http_client

    @property
    def base_url(self) -> str:
        """Return the configured Ollama base URL."""
        return self._base_url

    async def check_health(self) -> LLMStatusResponse:
        """Check whether the local Ollama server is reachable and the configured model is installed."""
        url = f"{self._base_url}/api/tags"
        try:
            payload = await self._request_json("GET", url)
        except LLMProviderError:
            return LLMStatusResponse(
                provider=self.PROVIDER_NAME,
                model=self.model_name,
                service_reachable=False,
                model_available=False,
                status="unavailable",
                message="Local Ollama service is unreachable. Ensure 'ollama serve' is running.",
            )

        raw_models = payload.get("models")
        installed_names: set[str] = set()
        if isinstance(raw_models, list):
            for entry in raw_models:
                if isinstance(entry, dict):
                    name = entry.get("name") or entry.get("model")
                    if isinstance(name, str) and name.strip():
                        installed_names.add(name.strip().lower())

        target_lower = self.model_name.strip().lower()
        model_found = target_lower in installed_names or any(
            installed.startswith(f"{target_lower}:") for installed in installed_names
        )

        if model_found:
            return LLMStatusResponse(
                provider=self.PROVIDER_NAME,
                model=self.model_name,
                service_reachable=True,
                model_available=True,
                status="ready",
                message=f"Ollama is running and model '{self.model_name}' is available.",
            )

        return LLMStatusResponse(
            provider=self.PROVIDER_NAME,
            model=self.model_name,
            service_reachable=True,
            model_available=False,
            status="model_missing",
            message=(
                f"Ollama is running, but model '{self.model_name}' is not installed. "
                f"Run 'ollama pull {self.model_name}'."
            ),
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
        """Send a non-streaming POST /api/generate request to Ollama and return the response string."""
        url = f"{self._base_url}/api/generate"
        options: dict[str, Any] = {
            "temperature": temperature if temperature is not None else self._default_temperature,
        }
        if max_tokens is not None and max_tokens > 0:
            options["num_predict"] = int(max_tokens)

        request_body: dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
        if system_prompt and system_prompt.strip():
            request_body["system"] = system_prompt.strip()

        payload = await self._request_json("POST", url, json_body=request_body)

        # Check if Ollama returned an application-level error inside a 200 payload
        if isinstance(payload.get("error"), str) and payload["error"].strip():
            err_text = payload["error"].strip()
            if "not found" in err_text.lower():
                raise LLMModelNotFoundError(self.model_name, provider=self.PROVIDER_NAME)
            raise LLMInvalidResponseError(
                "The local AI service reported a generation error.",
                provider=self.PROVIDER_NAME,
            )

        raw_response = payload.get("response")
        if not isinstance(raw_response, str):
            logger.warning(
                "Ollama response missing string 'response' field for model=%s.",
                self.model_name,
            )
            raise LLMInvalidResponseError(
                "The local AI service returned a malformed response payload.",
                provider=self.PROVIDER_NAME,
            )

        return raw_response

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request against Ollama and handle timeouts, connection errors, and 404s."""
        try:
            if self._http_client is not None:
                response = await self._http_client.request(
                    method, url, json=json_body, timeout=self._timeout
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout, trust_env=False) as client:
                    response = await client.request(method, url, json=json_body)

            if response.status_code == 404:
                # Inspect body to distinguish model-not-found vs invalid endpoint
                error_detail = ""
                try:
                    err_json = response.json()
                    if isinstance(err_json, dict) and isinstance(err_json.get("error"), str):
                        error_detail = err_json["error"].lower()
                except ValueError:
                    error_detail = response.text.lower()

                if "model" in error_detail or "not found" in error_detail:
                    logger.warning("Ollama model '%s' not found (HTTP 404).", self.model_name)
                    raise LLMModelNotFoundError(self.model_name, provider=self.PROVIDER_NAME)

                raise LLMInvalidResponseError(
                    "The local AI service endpoint was not found.",
                    provider=self.PROVIDER_NAME,
                )

            response.raise_for_status()
            data = response.json()
        except LLMProviderError:
            raise
        except httpx.TimeoutException as exc:
            logger.warning(
                "Ollama request timed out (model=%s, exc=%s).",
                self.model_name,
                type(exc).__name__,
            )
            raise LLMTimeoutError(provider=self.PROVIDER_NAME) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.warning(
                "Ollama returned HTTP %d for model=%s.",
                status_code,
                self.model_name,
            )
            raise LLMInvalidResponseError(
                "The local AI service returned an unexpected HTTP status.",
                provider=self.PROVIDER_NAME,
            ) from exc
        except httpx.RequestError as exc:
            logger.warning(
                "Ollama service unreachable (%s).",
                type(exc).__name__,
            )
            raise LLMServiceUnavailableError(provider=self.PROVIDER_NAME) from exc
        except ValueError as exc:
            logger.warning("Ollama returned malformed non-JSON response.")
            raise LLMInvalidResponseError(
                "The local AI service returned malformed JSON.",
                provider=self.PROVIDER_NAME,
            ) from exc

        if not isinstance(data, dict):
            logger.warning("Ollama JSON root is not an object.")
            raise LLMInvalidResponseError(
                "The local AI service returned an unexpected JSON structure.",
                provider=self.PROVIDER_NAME,
            )

        return data

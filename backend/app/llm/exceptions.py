"""Controlled exceptions for LLM providers without exposing internal server details."""

from http import HTTPStatus


class LLMProviderError(Exception):
    """Base exception for all LLM provider errors with safe user-facing messages."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "ollama",
        status_code: int = HTTPStatus.BAD_GATEWAY,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.message = message
        self.status_code = status_code


class LLMServiceUnavailableError(LLMProviderError):
    """Raised when the local LLM service (e.g., Ollama) is unreachable or offline."""

    def __init__(
        self,
        message: str = "The local AI service is currently unavailable. Please ensure Ollama is running.",
        *,
        provider: str = "ollama",
    ) -> None:
        super().__init__(
            message=message,
            provider=provider,
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )


class LLMTimeoutError(LLMProviderError):
    """Raised when an LLM generation request exceeds the configured timeout."""

    def __init__(
        self,
        message: str = "The local AI model timed out while generating a response.",
        *,
        provider: str = "ollama",
    ) -> None:
        super().__init__(
            message=message,
            provider=provider,
            status_code=HTTPStatus.GATEWAY_TIMEOUT,
        )


class LLMModelNotFoundError(LLMProviderError):
    """Raised when the requested LLM model is not installed or unavailable in the provider."""

    def __init__(
        self,
        model_name: str,
        *,
        provider: str = "ollama",
    ) -> None:
        if provider == "gemini":
            msg = f"Gemini model '{model_name}' was not found or is unavailable for this API key."
        else:
            msg = (
                f"Required AI model '{model_name}' is not installed locally. "
                f"Run 'ollama pull {model_name}' to install it."
            )
        super().__init__(
            message=msg,
            provider=provider,
            status_code=HTTPStatus.NOT_FOUND,
        )
        self.model_name = model_name


class LLMInvalidResponseError(LLMProviderError):
    """Raised when the LLM service returns malformed JSON, an empty response, or an unexpected payload."""

    def __init__(
        self,
        message: str = "The local AI service returned an invalid or empty response.",
        *,
        provider: str = "ollama",
    ) -> None:
        super().__init__(
            message=message,
            provider=provider,
            status_code=HTTPStatus.BAD_GATEWAY,
        )


class LLMStructuredOutputError(LLMProviderError):
    """Raised when the LLM fails to produce schema-valid JSON within the bounded retry limit."""

    def __init__(
        self,
        message: str = (
            "The AI model did not return a valid structured response matching the required schema "
            "after the maximum number of attempts."
        ),
        *,
        provider: str = "ollama",
        attempts: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            provider=provider,
            status_code=HTTPStatus.BAD_GATEWAY,
        )
        self.attempts = attempts

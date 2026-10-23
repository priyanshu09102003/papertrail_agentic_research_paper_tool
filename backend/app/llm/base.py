"""Workflow-independent LLM provider abstraction with Pydantic output validation and bounded retries."""

from abc import ABC, abstractmethod
import json
import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import (
    OLLAMA_DEFAULT_MAX_TOKENS,
    OLLAMA_DEFAULT_TEMPERATURE,
    OLLAMA_HARD_MAX_RETRIES_CAP,
    OLLAMA_MAX_PROMPT_CHARS,
    OLLAMA_MAX_STRUCTURED_RETRIES,
)
from app.llm.exceptions import (
    LLMInvalidResponseError,
    LLMStructuredOutputError,
)
from app.schemas import LLMStatusResponse, LLMTextResponse

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def extract_json_payload(raw_text: str) -> Any:
    """Parse JSON from raw model text, tolerating markdown code fences or surrounding prose.

    Raises ValueError if no valid JSON object or array can be extracted.
    """
    cleaned = raw_text.strip()
    if not cleaned:
        raise ValueError("Model returned empty text instead of JSON.")

    # 1. Try direct JSON parsing first
    try:
        return json.loads(cleaned)
    except ValueError:
        pass

    # 2. Try extracting inside ```json ... ``` markdown code fences
    fence_match = _CODE_FENCE_RE.search(cleaned)
    if fence_match:
        fenced_body = fence_match.group(1).strip()
        try:
            return json.loads(fenced_body)
        except ValueError:
            pass

    # 3. Try locating the outermost JSON object '{...}'
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = cleaned[first_brace : last_brace + 1]
        try:
            return json.loads(candidate)
        except ValueError:
            pass

    # 4. If output was truncated by max_tokens mid-object, salvage completed top-level key-value pairs
    if first_brace != -1:
        fragment = cleaned[first_brace:]
        comma_pos = fragment.rfind(",")
        while comma_pos > 0:
            candidate = fragment[:comma_pos].rstrip() + "}"
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict) and len(parsed) >= 1:
                    return parsed
            except ValueError:
                pass
            comma_pos = fragment.rfind(",", 0, comma_pos)

    raise ValueError("Could not parse a valid JSON object from model output.")


def _build_compact_json_template(response_model: type[BaseModel]) -> str:
    """Build a concise JSON key/type template that small local models follow accurately."""
    custom_tpl = getattr(response_model, "__compact_json_template__", None)
    if isinstance(custom_tpl, str) and custom_tpl.strip():
        return custom_tpl.strip()
    schema = response_model.model_json_schema()
    defs = schema.get("$defs", {})

    def _sample_for_prop(prop: dict[str, Any]) -> Any:
        if "$ref" in prop:
            ref_name = str(prop["$ref"]).split("/")[-1]
            ref_schema = defs.get(ref_name, {})
            return {
                k: _sample_for_prop(v)
                for k, v in ref_schema.get("properties", {}).items()
                if isinstance(v, dict)
            }

        if "anyOf" in prop and isinstance(prop["anyOf"], list):
            for option in prop["anyOf"]:
                if isinstance(option, dict) and option.get("type") != "null":
                    return _sample_for_prop(option)
            return None

        field_type = prop.get("type")
        if field_type == "array":
            items_prop = prop.get("items", {})
            if isinstance(items_prop, dict) and ("$ref" in items_prop or items_prop.get("type") == "object"):
                return [_sample_for_prop(items_prop)]
            return ["string"]
        if field_type == "number":
            return 0.9
        if field_type == "integer":
            return 1
        if field_type == "boolean":
            return True
        return "string"

    properties = schema.get("properties", {})
    template: dict[str, Any] = {}
    for field_name, prop in properties.items():
        if isinstance(prop, dict):
            if prop.get("exclude_from_prompt") is True:
                continue
            template[field_name] = _sample_for_prop(prop)
        else:
            template[field_name] = "string"
    return json.dumps(template, separators=(",", ":"))


class BaseLLMProvider(ABC):
    """Abstract base class for local or hosted LLM providers.

    Kept independent of any specific research workflow or agent orchestration.
    """

    def __init__(
        self,
        *,
        provider_name: str,
        model_name: str,
        default_temperature: float = OLLAMA_DEFAULT_TEMPERATURE,
        max_structured_retries: int = OLLAMA_MAX_STRUCTURED_RETRIES,
        max_prompt_chars: int = OLLAMA_MAX_PROMPT_CHARS,
    ) -> None:
        self._provider_name = provider_name
        self._model_name = model_name
        self._default_temperature = default_temperature
        self._max_structured_retries = self._clamp_retries(max_structured_retries)
        self._max_prompt_chars = max_prompt_chars

    @property
    def provider_name(self) -> str:
        """Return the identifier of the LLM provider."""
        return self._provider_name

    @property
    def model_name(self) -> str:
        """Return the configured model name."""
        return self._model_name

    @staticmethod
    def _clamp_retries(retries: int) -> int:
        """Clamp retry counts to [0, OLLAMA_HARD_MAX_RETRIES_CAP] to prevent unbounded loops."""
        return max(0, min(int(retries), OLLAMA_HARD_MAX_RETRIES_CAP))

    def _validate_prompt(self, prompt: str) -> str:
        """Validate that the prompt is non-empty and within character limits."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string.")
        cleaned = prompt.strip()
        if len(cleaned) > self._max_prompt_chars:
            raise ValueError(
                f"Prompt length ({len(cleaned)} chars) exceeds maximum allowed limit "
                f"({self._max_prompt_chars} chars)."
            )
        return cleaned

    @abstractmethod
    async def _raw_generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        """Execute a single low-level generation call and return raw text."""

    @abstractmethod
    async def check_health(self) -> LLMStatusResponse:
        """Check whether the provider service and configured model are available."""

    async def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMTextResponse:
        """Generate a plain-text completion and validate the output with Pydantic."""
        validated_prompt = self._validate_prompt(prompt)
        raw_text = await self._raw_generate(
            validated_prompt,
            system_prompt=system_prompt,
            temperature=temperature if temperature is not None else self._default_temperature,
            max_tokens=max_tokens or OLLAMA_DEFAULT_MAX_TOKENS,
            json_mode=False,
        )

        cleaned_text = raw_text.strip()
        if not cleaned_text:
            raise LLMInvalidResponseError(
                "The local AI model returned an empty text response.",
                provider=self._provider_name,
            )

        try:
            return LLMTextResponse(
                provider=self._provider_name,
                model=self._model_name,
                text=cleaned_text,
            )
        except ValidationError as exc:
            logger.warning(
                "LLMTextResponse Pydantic validation failed for provider=%s model=%s.",
                self._provider_name,
                self._model_name,
            )
            raise LLMInvalidResponseError(
                "The local AI model output failed response validation.",
                provider=self._provider_name,
            ) from exc

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_retries: int | None = None,
    ) -> T:
        """Generate structured JSON output and validate against a Pydantic model with bounded retries.

        Never trusts the model to follow JSON instructions blindly and never loops unboundedly.
        """
        validated_prompt = self._validate_prompt(prompt)
        bounded_retries = (
            self._clamp_retries(max_retries)
            if max_retries is not None
            else self._max_structured_retries
        )
        max_attempts = 1 + bounded_retries

        required_keys = [
            k
            for k, v in response_model.model_json_schema().get("properties", {}).items()
            if not (isinstance(v, dict) and v.get("exclude_from_prompt") is True)
        ]
        compact_template = _build_compact_json_template(response_model)
        base_system_instruction = (
            f"{system_prompt.strip()}\n" if system_prompt and system_prompt.strip() else ""
        ) + "Respond ONLY with a valid single-line JSON object. No prose, no markdown fences."

        current_prompt = (
            f"{validated_prompt}\n\n"
            f"Return ONLY a single-line JSON object matching: {compact_template}"
        )
        for attempt in range(1, max_attempts + 1):
            raw_output = await self._raw_generate(
                current_prompt,
                system_prompt=base_system_instruction,
                temperature=temperature if temperature is not None else self._default_temperature,
                max_tokens=max_tokens or 512,
                json_mode=True,
            )

            try:
                parsed_json = extract_json_payload(raw_output)
                return response_model.model_validate(parsed_json)
            except (ValueError, ValidationError) as exc:
                error_kind = "ValidationError" if isinstance(exc, ValidationError) else "JSONDecodeError"
                logger.warning(
                    "Structured output validation failed (provider=%s, model=%s, schema=%s, "
                    "attempt=%d/%d, error=%s).",
                    self._provider_name,
                    self._model_name,
                    response_model.__name__,
                    attempt,
                    max_attempts,
                    error_kind,
                )

                if attempt >= max_attempts:
                    raise LLMStructuredOutputError(
                        message=(
                            f"The AI model failed to produce valid '{response_model.__name__}' "
                            f"JSON after {max_attempts} bounded attempt(s)."
                        ),
                        provider=self._provider_name,
                        attempts=max_attempts,
                    ) from exc

                feedback_summary = (
                    str(exc.errors()[0].get("msg", "Invalid schema fields"))
                    if isinstance(exc, ValidationError) and exc.errors()
                    else "Output was not valid JSON"
                )
                current_prompt = (
                    f"{validated_prompt}\n\n"
                    f"Correction needed (attempt {attempt + 1}/{max_attempts}): {feedback_summary}. "
                    f"Return ONLY a JSON object with keys {required_keys} like: {compact_template}"
                )

        raise LLMStructuredOutputError(
            provider=self._provider_name,
            attempts=max_attempts,
        )

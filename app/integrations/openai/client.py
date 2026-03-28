from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from app.core.config import get_settings


StructuredOutputT = TypeVar("StructuredOutputT", bound=BaseModel)


class OpenAiIntegrationError(RuntimeError):
    def __init__(self, message: str, *, code: str = "provider_error") -> None:
        super().__init__(message)
        self.code = code


class OpenAiConfigurationError(OpenAiIntegrationError):
    pass


class OpenAiLlmClient:
    provider_name = "openai"

    def is_available(self) -> bool:
        settings = get_settings()
        return bool(settings.openai_llm_enabled and settings.openai_api_key)

    def parse_chat_completion(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_format: type[StructuredOutputT],
        max_completion_tokens: int,
        reasoning_effort: str | None = None,
        verbosity: str = "low",
        timeout_seconds: float | None = None,
    ) -> StructuredOutputT:
        settings = get_settings()
        if not settings.openai_llm_enabled:
            raise OpenAiConfigurationError("OpenAI LLM integration is disabled.", code="llm_disabled")
        if not settings.openai_api_key:
            raise OpenAiConfigurationError("OPENAI_API_KEY is not configured.", code="missing_api_key")
        request_timeout = float(timeout_seconds or settings.openai_timeout_seconds)

        try:
            from openai import OpenAI
            from openai import APIConnectionError, APIStatusError, APITimeoutError, LengthFinishReasonError, RateLimitError
        except Exception as exc:  # pragma: no cover - import guard for local env mismatch
            raise OpenAiIntegrationError("OpenAI SDK is not installed.", code="sdk_not_installed") from exc

        client = OpenAI(
            api_key=settings.openai_api_key,
            max_retries=settings.openai_max_retries,
            timeout=request_timeout,
        )
        try:
            request_kwargs: dict[str, object] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": response_format,
                "max_completion_tokens": max_completion_tokens,
                "verbosity": verbosity,
                "timeout": request_timeout,
            }
            if reasoning_effort:
                request_kwargs["reasoning_effort"] = reasoning_effort
            completion = client.chat.completions.parse(
                **request_kwargs,
            )
        except APITimeoutError as exc:
            raise OpenAiIntegrationError("OpenAI request timed out.", code="timeout") from exc
        except APIConnectionError as exc:
            raise OpenAiIntegrationError("OpenAI connection failed.", code="connection_error") from exc
        except RateLimitError as exc:
            raise OpenAiIntegrationError("OpenAI rate limit reached.", code="rate_limited") from exc
        except LengthFinishReasonError as exc:
            raise OpenAiIntegrationError("OpenAI response hit a length limit.", code="length_limit") from exc
        except APIStatusError as exc:
            error_code, error_message = _extract_api_error_details(exc)
            raise OpenAiIntegrationError(error_message, code=error_code) from exc
        except Exception as exc:
            raise OpenAiIntegrationError(str(exc) or "OpenAI request failed.", code="provider_error") from exc

        if not completion.choices:
            raise OpenAiIntegrationError("OpenAI returned no choices.", code="empty_response")
        message = completion.choices[0].message
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise OpenAiIntegrationError("OpenAI refused the request.", code="refusal")
        parsed = getattr(message, "parsed", None)
        if parsed is None:
            raise OpenAiIntegrationError("OpenAI returned no structured output.", code="structured_output_missing")
        return parsed


def _extract_api_error_details(exc: Exception) -> tuple[str, str]:
    default_code = "provider_error"
    default_message = "OpenAI returned an API error."

    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error_payload = body.get("error")
        if isinstance(error_payload, dict):
            error_code = error_payload.get("code")
            error_message = error_payload.get("message")
            if isinstance(error_code, str) and error_code.strip():
                default_code = error_code.strip()
            if isinstance(error_message, str) and error_message.strip():
                default_message = error_message.strip()

    return default_code, default_message

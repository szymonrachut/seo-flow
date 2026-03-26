from __future__ import annotations

from dataclasses import dataclass
import json

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.core.text_processing import collapse_whitespace
from app.integrations.openai.client import OpenAiConfigurationError, OpenAiIntegrationError, OpenAiLlmClient
from app.services.competitive_gap_language_service import output_language_instruction
from app.services.content_generator_context_service import ContentGeneratorPromptContext


CONTENT_GENERATOR_PROMPT_VERSION = "content-generator-assets-v1"
CONTENT_GENERATOR_COMPLETION_LIMITS = (1600, 2400)
GENERIC_HOOK_PREFIXES = (
    "in this article",
    "in this guide",
    "this article",
    "this guide",
    "w tym artykule",
    "w tym poradniku",
    "w tym wpisie",
    "w tym tekscie",
    "ten artykul",
)


class ContentGeneratorPromptServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "content_generator_prompt_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class GeneratedContentAssets:
    surfer_custom_instructions: str
    seowriting_details_to_include: str
    introductory_hook_brief: str
    llm_provider: str
    llm_model: str
    prompt_version: str


class _ContentGeneratorOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    surfer_custom_instructions: str = Field(min_length=240, max_length=4500)
    seowriting_details_to_include: str = Field(min_length=80, max_length=1000)
    introductory_hook_brief: str = Field(min_length=40, max_length=500)


def generate_content_assets(
    context: ContentGeneratorPromptContext,
    *,
    client: OpenAiLlmClient | None = None,
    output_language: str = "en",
) -> GeneratedContentAssets:
    settings = get_settings()
    llm_model = settings.openai_model_content_generator
    resolved_client = client or OpenAiLlmClient()
    if not resolved_client.is_available():
        raise ContentGeneratorPromptServiceError(_resolve_unavailable_message(), code=_resolve_unavailable_code())

    parsed = None
    last_error: OpenAiIntegrationError | None = None
    try:
        for completion_limit in CONTENT_GENERATOR_COMPLETION_LIMITS:
            try:
                parsed = resolved_client.parse_chat_completion(
                    model=llm_model,
                    system_prompt=_content_generator_system_prompt(output_language=output_language),
                    user_prompt=_content_generator_user_prompt(context),
                    response_format=_ContentGeneratorOutput,
                    max_completion_tokens=completion_limit,
                    reasoning_effort="low",
                    verbosity="low",
                )
                break
            except OpenAiIntegrationError as exc:
                last_error = exc
                if exc.code == "length_limit" and completion_limit != CONTENT_GENERATOR_COMPLETION_LIMITS[-1]:
                    continue
                raise
    except OpenAiConfigurationError as exc:
        raise ContentGeneratorPromptServiceError(str(exc), code=exc.code) from exc
    except OpenAiIntegrationError as exc:
        raise ContentGeneratorPromptServiceError(str(exc), code=exc.code) from exc

    if parsed is None:
        fallback_exc = last_error or OpenAiIntegrationError(
            "Content generator returned no structured output.",
            code="structured_output_missing",
        )
        raise ContentGeneratorPromptServiceError(str(fallback_exc), code=fallback_exc.code)

    return _sanitize_output(
        parsed,
        llm_provider=getattr(resolved_client, "provider_name", "openai"),
        llm_model=llm_model,
    )


def _sanitize_output(
    parsed: _ContentGeneratorOutput,
    *,
    llm_provider: str,
    llm_model: str,
) -> GeneratedContentAssets:
    surfer_custom_instructions = _normalize_multiline_text(parsed.surfer_custom_instructions)
    seowriting_details_to_include = _normalize_multiline_text(parsed.seowriting_details_to_include)
    introductory_hook_brief = collapse_whitespace(parsed.introductory_hook_brief)

    if len(surfer_custom_instructions) < 240:
        raise ContentGeneratorPromptServiceError(
            "Generated Surfer instructions are too short to be useful.",
            code="surfer_instructions_too_short",
        )
    if len(seowriting_details_to_include) < 80:
        raise ContentGeneratorPromptServiceError(
            "Generated SEO Writing details are too short to be useful.",
            code="details_too_short",
        )
    if len(introductory_hook_brief) > 500:
        raise ContentGeneratorPromptServiceError(
            "Generated hook brief exceeded the 500 character limit.",
            code="hook_too_long",
        )
    if _looks_generic_hook(introductory_hook_brief):
        raise ContentGeneratorPromptServiceError(
            "Generated hook brief fell back to a generic article opener.",
            code="generic_hook_brief",
        )

    return GeneratedContentAssets(
        surfer_custom_instructions=surfer_custom_instructions,
        seowriting_details_to_include=seowriting_details_to_include,
        introductory_hook_brief=introductory_hook_brief,
        llm_provider=llm_provider,
        llm_model=llm_model,
        prompt_version=CONTENT_GENERATOR_PROMPT_VERSION,
    )


def _looks_generic_hook(value: str) -> bool:
    normalized = collapse_whitespace(value).lower()
    return any(normalized.startswith(prefix) for prefix in GENERIC_HOOK_PREFIXES)


def _normalize_multiline_text(value: str) -> str:
    lines = [
        collapse_whitespace(line)
        for line in str(value or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
    cleaned_lines: list[str] = []
    previous_blank = False
    for line in lines:
        if not line:
            if cleaned_lines and not previous_blank:
                cleaned_lines.append("")
            previous_blank = True
            continue
        cleaned_lines.append(line)
        previous_blank = False
    return "\n".join(cleaned_lines).strip()


def _content_generator_system_prompt(*, output_language: str) -> str:
    return (
        "You generate site-level brand-safe writing instructions for SEO content tools.\n"
        f"{output_language_instruction(output_language)}\n"
        "Return valid JSON that matches the required schema.\n"
        "Base every factual statement only on the provided source pages, page metadata and GSC queries.\n"
        "Do not invent certifications, awards, years of experience, locations, team size, processes, guarantees, "
        "results, pricing, technologies, or differentiators unless the source payload states them explicitly.\n"
        "If evidence is thin, stay cautious and describe only what is clearly supported by the inputs.\n"
        "The Surfer instructions must explain: who the brand is, who it writes for, tone of voice, how to present "
        "the offer, what to avoid, CTA rules, internal linking rules, and a strict anti-hallucination rule.\n"
        "The SEO Writing details must be compact, information-dense and practical.\n"
        "The hook brief must stay below 500 characters, avoid generic article openers, and avoid invented claims.\n"
        "Never mention missing facts as facts. Prefer 'only mention verified details visible in the source pages' when needed."
    )


def _content_generator_user_prompt(context: ContentGeneratorPromptContext) -> str:
    payload = {
        "prompt_version": CONTENT_GENERATOR_PROMPT_VERSION,
        "task": "Generate three content assets for a single site using only the provided snapshot context.",
        "requirements": {
            "surfer_custom_instructions": "Practical strategic block, ideally 2000-4500 characters, no fluff.",
            "seowriting_details_to_include": "Compact and dense, target roughly <=1000 characters.",
            "introductory_hook_brief": "Max 500 characters. Must avoid generic openers such as 'In this article' or 'W tym artykule'.",
        },
        "context": context.prompt_payload,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _resolve_unavailable_code() -> str:
    settings = get_settings()
    if not settings.openai_llm_enabled:
        return "llm_disabled"
    if not settings.openai_api_key:
        return "missing_api_key"
    return "llm_unavailable"


def _resolve_unavailable_message() -> str:
    code = _resolve_unavailable_code()
    if code == "llm_disabled":
        return "OpenAI LLM integration is disabled."
    if code == "missing_api_key":
        return "OPENAI_API_KEY is not configured."
    return "OpenAI content generator is unavailable."

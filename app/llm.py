import logging
from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import settings
from app.guards import llm_semaphore, increment_total_llm_calls

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class UpstreamUnavailable(Exception):
    """Raised when primary and fallback LLM providers return 429/5xx, missing key, or network errors."""
    pass


class SchemaValidationFailed(Exception):
    """Raised when the LLM response fails to parse into the required Pydantic schema."""
    pass


def get_llm(provider: str):
    provider_name = provider.lower()
    if provider_name == "gemini":
        if not settings.GEMINI_API_KEY:
            raise UpstreamUnavailable("GEMINI_API_KEY is not set in environment or .env file.")
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0
        )
    elif provider_name == "openai":
        if not settings.OPENAI_API_KEY:
            raise UpstreamUnavailable("OPENAI_API_KEY is not set in environment or .env file.")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            temperature=0
        )
    elif provider_name == "groq":
        if not settings.GROQ_API_KEY:
            raise UpstreamUnavailable("GROQ_API_KEY is not set in environment or .env file.")
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.1-8b-instant",
            groq_api_key=settings.GROQ_API_KEY,
            temperature=0
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


async def _call_llm_with_provider(provider: str, system: str, user: str, schema: Type[T]) -> T:
    # Acquire global semaphore (max 2 concurrent outbound LLM calls)
    async with llm_semaphore:
        increment_total_llm_calls()
        llm = get_llm(provider)
        structured_llm = llm.with_structured_output(schema)
        messages = [SystemMessage(content=system), HumanMessage(content=user)]
        return await structured_llm.ainvoke(messages)


async def complete(system: str, user: str, schema: Type[T]) -> T:
    """
    Single entry point for structured LLM output generation.
    Enforces global Semaphore(2) concurrency and increments call counter.
    Handles primary/fallback provider retries on API errors (429/5xx) and schema validation retries.
    Never returns raw model text to callers.
    """
    primary_provider = settings.LLM_PROVIDER
    fallback_provider = settings.FALLBACK_PROVIDER

    for schema_attempt in range(2):
        try:
            try:
                return await _call_llm_with_provider(primary_provider, system, user, schema)
            except UpstreamUnavailable:
                if fallback_provider:
                    try:
                        return await _call_llm_with_provider(fallback_provider, system, user, schema)
                    except Exception as fb_err:
                        raise UpstreamUnavailable(f"Primary and fallback providers unavailable: {fb_err}")
                raise
            except (ValidationError, Exception) as err:
                err_str = str(err).lower()
                is_api_err = any(code in err_str for code in ["429", "500", "502", "503", "504", "rate limit", "quota", "connection", "api_key"])
                
                if is_api_err and fallback_provider:
                    try:
                        return await _call_llm_with_provider(fallback_provider, system, user, schema)
                    except (ValidationError, Exception) as fb_err:
                        fb_err_str = str(fb_err).lower()
                        if any(code in fb_err_str for code in ["429", "500", "502", "503", "504", "rate limit", "quota"]):
                            raise UpstreamUnavailable(f"Primary and fallback providers failed: {fb_err}")
                        raise SchemaValidationFailed(f"Fallback provider schema parsing failed: {fb_err}")
                elif is_api_err:
                    raise UpstreamUnavailable(f"Primary LLM provider API error: {err}")
                else:
                    if schema_attempt == 1:
                        raise SchemaValidationFailed(f"Response failed schema validation after retry: {err}")
        except (UpstreamUnavailable, SchemaValidationFailed):
            raise
        except Exception as e:
            if schema_attempt == 1:
                raise SchemaValidationFailed(f"Failed to generate structured response: {e}")

    raise SchemaValidationFailed("Response failed schema validation.")

import logging
from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class UpstreamUnavailable(Exception):
    """Raised when primary and fallback LLM providers return 429/5xx or network errors."""
    pass


class SchemaValidationFailed(Exception):
    """Raised when the LLM response fails to parse into the required Pydantic schema."""
    pass


def get_llm(provider: str):
    provider_name = provider.lower()
    if provider_name == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0
        )
    elif provider_name == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            temperature=0
        )
    elif provider_name == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.1-8b-instant",
            groq_api_key=settings.GROQ_API_KEY,
            temperature=0
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


async def _call_llm_with_provider(provider: str, system: str, user: str, schema: Type[T]) -> T:
    llm = get_llm(provider)
    structured_llm = llm.with_structured_output(schema)
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    return await structured_llm.ainvoke(messages)


async def complete(system: str, user: str, schema: Type[T]) -> T:
    """
    Single entry point for structured LLM output generation.
    Handles primary/fallback provider retries on API errors (429/5xx) and schema validation retries.
    Never returns raw model text to callers.
    """
    primary_provider = settings.LLM_PROVIDER
    fallback_provider = settings.FALLBACK_PROVIDER

    # Attempt execution with primary provider
    for schema_attempt in range(2):
        try:
            try:
                return await _call_llm_with_provider(primary_provider, system, user, schema)
            except (ValidationError, Exception) as err:
                # Distinguish API/network errors from schema validation errors
                err_str = str(err).lower()
                is_api_err = any(code in err_str for code in ["429", "500", "502", "503", "504", "rate limit", "quota", "connection"])
                
                if is_api_err and fallback_provider:
                    # Retry once with fallback provider on API error
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
                    # If it's a schema validation error, loop to retry once
                    if schema_attempt == 1:
                        raise SchemaValidationFailed(f"Response failed schema validation after retry: {err}")
        except (UpstreamUnavailable, SchemaValidationFailed):
            raise
        except Exception as e:
            if schema_attempt == 1:
                raise SchemaValidationFailed(f"Failed to generate structured response: {e}")

    raise SchemaValidationFailed("Response failed schema validation.")

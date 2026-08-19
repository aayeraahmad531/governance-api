import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Optional
from fastapi import HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

# SlowAPI Limiter configured per IP
limiter = Limiter(key_func=get_remote_address)

# Global concurrency semaphore for LLM calls (maximum 2 concurrent requests)
llm_semaphore = asyncio.Semaphore(2)


class LRUCache:
    def __init__(self, maxsize: int = 500, ttl: int = 86400):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def _make_key(self, payload: dict) -> str:
        normalized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get(self, payload: dict) -> Optional[Any]:
        key = self._make_key(payload)
        if key not in self.cache:
            return None
        timestamp, value = self.cache[key]
        if time.time() - timestamp > self.ttl:
            del self.cache[key]
            return None
        self.cache.move_to_end(key)
        return value

    def set(self, payload: dict, value: Any) -> None:
        key = self._make_key(payload)
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = (time.time(), value)
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)


response_cache = LRUCache(
    maxsize=settings.CACHE_MAX_ENTRIES,
    ttl=settings.CACHE_TTL_SECONDS
)


def validate_text_length(text: str, max_length: int = 2000) -> None:
    """Rejects text fields over 2000 chars with HTTP 422."""
    if len(text) > max_length:
        raise HTTPException(
            status_code=422,
            detail=f"Input text exceeds maximum allowed length of {max_length} characters."
        )


def clamp_num_questions(n: int) -> int:
    """Clamps num_questions to 1..3."""
    return max(1, min(3, n))

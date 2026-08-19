# governance-api

Unified governance FastAPI service wrapping AI auditing tools:
- **`POST /api/bias`**: Audits job descriptions for gender, age, and cultural bias.
- **`POST /api/compliance`**: Audits AI systems against EU AI Act principles.
- **`POST /api/hallucination`**: Measures LLM hallucination rates on indexed topics.

## Phase 1 Architecture & Features

- **FastAPI Framework**: Clean router modularity, Pydantic settings management, and custom exception handling.
- **Privacy Commitment**: Zero request body or prompt/completion logging. Logs capture **only** `timestamp`, `path`, `status`, and `duration`.
- **CORS Configuration**: Strict explicit comma-separated origin handling without wildcards (`ALLOWED_ORIGINS`).
- **Guards**:
  - SlowAPI IP rate limiter (5 requests/hour/IP).
  - Global `asyncio.Semaphore(2)` concurrency ceiling for LLM calls.
  - In-memory SHA256 LRU cache (24h TTL, 500 entries max).
  - Input text caps (max 2000 characters).

> **Testing Note on Guards**:
> The `asyncio.Semaphore(2)` concurrency limit and response LRU cache are active in `app/guards.py`. Full test coverage for both will be introduced in **Phase 3** when live LLM completions are connected.

## Local Execution & Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python -m uvicorn app.main:app --port 8080 --reload

# Run test suite
python -m pytest -o pythonpath=. -v tests/
```

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

## Scoring Methodology & Architectural Design Choices

### Single-Category Score Ceiling (0.40 Capping)
The bias detection engine enforces a deliberate architectural ceiling: **single-category bias is capped at a maximum risk contribution of 0.40 / 1.00**, regardless of the volume of biased terms detected within that single category.

#### Design Rationale
- **Single-Dimension Jargon vs. Systemic Exclusion**: In real-world recruitment, a job posting containing multiple masculine-coded jargon terms (e.g., `ninja`, `rockstar`, `crush`, `killer`) represents isolated stylistic jargon within a single category (Gender). Un-capped scoring would cause a 4-term gender-biased posting to saturate at 1.00, obscuring the difference between single-category jargon and severe multi-dimensional exclusion.
- **Multi-Category Spread Elevation**: To accurately represent composite risk, postings that combine barriers across multiple demographic dimensions (e.g., Gender + Age + Cultural: `rockstar`, `young`, `Western`, `He`) are awarded category spread multipliers and bonuses to reach **1.00**.
- **Ordering Guarantee**: This design guarantees strict risk score ordering:
  - 3-Category Exclusionary Postings: **1.00**
  - 2-Category Exclusionary Postings: **0.60 – 0.70**
  - 1-Category Jargon-Heavy Postings: **0.40 Max**


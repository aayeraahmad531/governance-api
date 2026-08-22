import logging
from typing import List
from fastapi import APIRouter, Request
from app.guards import limiter, validate_text_length, response_cache, increment_dropped_bias_spans
from app.schemas import BiasRequest, BiasResponse, BiasSpan, CategoryFinding
from app.retrieval import search
from app.llm import complete

logger = logging.getLogger("governance_api.routers.bias")
router = APIRouter(prefix="/api", tags=["bias"])


SYSTEM_PROMPT = """You are an expert HR compliance auditor analyzing job descriptions for gender, age, and cultural bias.
Auditing Rules:
1. Examine the job description text against the provided retrieved bias lexicon entries.
2. Under 'spans', extract EVERY biased term or phrase. The 'text' field MUST be copied EXACTLY VERBATIM (character-for-character) from the input job description text so the UI can highlight it. Do not paraphrase.
3. Classify category into: gender, age, or cultural.
4. For each category, evaluate whether bias is detected, confidence (0.0-1.0), examples, and actionable replacement suggestions based on retrieved lexicon replacements.
5. Provide a concise summary of the audit findings.
"""


def compute_deterministic_bias_score(spans: List[BiasSpan], retrieved_lexicon_map: dict) -> float:
    """
    Computes overall_bias_score (0.0 - 1.0) deterministically.
    Excludes severity 'info' (feminine-coded) entries entirely from contributing to the score.
    """
    if not spans:
        return 0.0

    score = 0.0
    for span in spans:
        span_text_clean = span.text.strip().lower()
        meta = retrieved_lexicon_map.get(span_text_clean, {})
        severity = meta.get("severity", "medium").lower()

        # Exclude 'info' severity entries (feminine-coded terms) from score
        if severity == "info":
            continue
        elif severity == "high":
            score += 0.35
        elif severity == "medium":
            score += 0.20
        elif severity == "low":
            score += 0.10
        else:
            score += 0.15

    return min(1.0, round(score, 2))


@router.post("/bias", response_model=BiasResponse)
@limiter.limit("5/hour")
async def audit_bias(request: Request, body: BiasRequest) -> BiasResponse:
    validate_text_length(body.job_description)

    # Check cache first
    cache_payload = {
        "endpoint": "bias",
        "job_description": body.job_description,
        "analysis_type": sorted(body.analysis_type or ["gender", "age", "cultural"])
    }
    cached_res = response_cache.get(cache_payload)
    if cached_res is not None:
        logger.info("Cache hit for /api/bias request.")
        return BiasResponse(**cached_res)

    # Retrieval step: search bias_lexicon
    lexicon_hits = search("bias_lexicon", body.job_description, k=10)
    retrieved_lexicon_map = {}
    lexicon_context_lines = []
    for h in lexicon_hits:
        m = h.get("meta", {})
        term = m.get("term", "").lower()
        if term:
            retrieved_lexicon_map[term] = m
        lexicon_context_lines.append(
            f"- Term: '{m.get('term')}', Category: {m.get('category')}, Severity: {m.get('severity')}, Suggested replacement: '{m.get('replacement')}'"
        )

    user_prompt = f"""Retrieved Bias Lexicon Guide:
{chr(10).join(lexicon_context_lines)}

Job Description to Audit:
\"\"\"
{body.job_description}
\"\"\"
"""

    # Call LLM
    llm_res: BiasResponse = await complete(SYSTEM_PROMPT, user_prompt, BiasResponse)

    # Server-Side Verbatim Validation & Span Dropping
    valid_spans: List[BiasSpan] = []
    dropped_count = 0
    for span in llm_res.spans:
        if span.text in body.job_description:
            valid_spans.append(span)
        else:
            dropped_count += 1
            logger.warning(f"Dropping non-verbatim bias span: '{span.text}' (not found in input text)")

    if dropped_count > 0:
        increment_dropped_bias_spans(dropped_count)

    llm_res.spans = valid_spans

    # Deterministic overall_bias_score excluding severity 'info'
    llm_res.overall_bias_score = compute_deterministic_bias_score(valid_spans, retrieved_lexicon_map)

    # Store in response_cache
    response_cache.set(cache_payload, llm_res.model_dump())

    return llm_res

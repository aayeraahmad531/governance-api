import logging
from typing import List
from fastapi import APIRouter, Request
from app.guards import limiter, validate_text_length, response_cache, increment_dropped_bias_spans
from app.schemas import BiasRequest, BiasResponse, BiasSpan, CategoryFinding
from app.retrieval import search
from app.llm import complete, ACTIVE_MODEL_NAME

logger = logging.getLogger("governance_api.routers.bias")
router = APIRouter(prefix="/api", tags=["bias"])

SYSTEM_PROMPT = """You are an expert HR compliance auditor analyzing job descriptions for gender, age, and cultural bias.
Auditing Rules:
1. Examine the text against the provided bias lexicon entries.
2. Under 'spans', extract EVERY biased term. The 'text' field MUST be copied EXACTLY VERBATIM (character-for-character) from the input text.
3. Classify category: gender, age, or cultural.
4. Evaluate detected (boolean), confidence (0.0-1.0), examples, and replacement suggestions.
5. Provide a concise summary.
"""


def compute_deterministic_bias_score(spans: List[BiasSpan], retrieved_lexicon_map: dict) -> float:
    if not spans:
        return 0.0

    score = 0.0
    for span in spans:
        span_text_clean = span.text.strip().lower()
        meta = retrieved_lexicon_map.get(span_text_clean, {})
        severity = meta.get("severity", "medium").lower()

        if severity == "info":
            continue
        elif severity == "high":
            score += 0.35
        elif severity == "medium":
            score += 0.25
        elif severity == "low":
            score += 0.10
        else:
            score += 0.15

    return min(1.0, round(score, 2))


@router.post("/bias", response_model=BiasResponse)
@limiter.limit("5/hour")
async def audit_bias(request: Request, body: BiasRequest) -> BiasResponse:
    validate_text_length(body.job_description)

    cache_payload = {
        "endpoint": "bias",
        "job_description": body.job_description,
        "analysis_type": sorted(body.analysis_type or ["gender", "age", "cultural"])
    }
    cached_res = response_cache.get(cache_payload)
    if cached_res is not None:
        logger.info(f"Cache hit for /api/bias request. Served by model '{ACTIVE_MODEL_NAME}'.")
        return BiasResponse(**cached_res)

    lexicon_hits = search("bias_lexicon", body.job_description, k=5)
    retrieved_lexicon_map = {}
    lexicon_context_lines = []
    for h in lexicon_hits:
        m = h.get("meta", {})
        term = m.get("term", "").lower()
        if term:
            retrieved_lexicon_map[term] = m
        lexicon_context_lines.append(
            f"- Term: '{m.get('term')}', Category: {m.get('category')}, Severity: {m.get('severity')}, Suggested: '{m.get('replacement')}'"
        )

    user_prompt = f"""Bias Lexicon Guide:
{chr(10).join(lexicon_context_lines)}

Job Description:
\"\"\"
{body.job_description}
\"\"\"
"""

    llm_res: BiasResponse = await complete(SYSTEM_PROMPT, user_prompt, BiasResponse)

    valid_spans: List[BiasSpan] = []
    dropped_count = 0
    observations: List[str] = []

    for span in llm_res.spans:
        if span.text in body.job_description:
            valid_spans.append(span)
            span_clean = span.text.strip().lower()
            meta = retrieved_lexicon_map.get(span_clean, {})
            if meta.get("severity", "").lower() == "info":
                observations.append(
                    f"Feminine-coded term '{span.text}' noted under observations. Note: Inclusive phrasing is not a defect and does not affect the risk score."
                )
        else:
            dropped_count += 1
            logger.warning(f"Dropping non-verbatim bias span: '{span.text}' (not found in input text)")

    if dropped_count > 0:
        increment_dropped_bias_spans(dropped_count)

    # Post-process categories: If all matching spans for a category are severity "info", set detected = False
    for cat in llm_res.categories:
        cat_spans = [s for s in valid_spans if s.category.lower() == cat.bias_type.lower()]
        non_info_spans = [
            s for s in cat_spans
            if retrieved_lexicon_map.get(s.text.strip().lower(), {}).get("severity", "").lower() != "info"
        ]

        if cat_spans and not non_info_spans:
            cat.detected = False
            cat.confidence = 0.0
            cat.suggestion = "Inclusive phrasing detected; noted under observations without score defect."
        elif not cat_spans:
            cat.detected = False
            cat.confidence = 0.0

    llm_res.spans = valid_spans
    llm_res.observations = list(dict.fromkeys(observations))  # Deduplicate observations
    llm_res.overall_bias_score = compute_deterministic_bias_score(valid_spans, retrieved_lexicon_map)

    logger.info(f"/api/bias successfully audited request using serving model '{ACTIVE_MODEL_NAME}'.")
    response_cache.set(cache_payload, llm_res.model_dump())

    return llm_res

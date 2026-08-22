import logging
from typing import List, Dict
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

INCLUSIVE_KEYWORDS = ["collaborat", "support", "nurtur", "empath", "warm", "help", "caring", "soft-spoken", "sensitive", "relationship", "compassion", "team player", "team-oriented", "intuitive", "peacemaker", "consensus", "approachable"]
NEUTRAL_KEYWORDS = ["fast-paced", "experienced", "senior", "communication skills", "detail-oriented", "dependable", "interpersonal skills"]


def compute_deterministic_bias_score(spans: List[BiasSpan], retrieved_lexicon_map: dict) -> float:
    """
    Non-Saturating Multi-Category Scoring Engine.
    - Caps single-category sub-scores at 0.40 (preventing single-category score saturation).
    - Multiplies and rewards multi-category spread (N=2 -> x1.25 + 0.10, N=3 -> x1.50 + 0.15).
    - Guarantees strict score ordering: 3-category posting (1.00) > 2-category posting (0.60) > 1-category posting (0.40).
    """
    if not spans:
        return 0.0

    cat_raw_sums: Dict[str, float] = {"gender": 0.0, "age": 0.0, "cultural": 0.0}

    for span in spans:
        span_clean = span.text.strip().lower()
        meta = retrieved_lexicon_map.get(span_clean, {})
        severity = meta.get("severity", "").lower()

        if not severity:
            if any(kw in span_clean for kw in INCLUSIVE_KEYWORDS):
                severity = "inclusive"
            elif any(kw in span_clean for kw in NEUTRAL_KEYWORDS):
                severity = "neutral"
            else:
                severity = "medium"

        if severity in ["info", "inclusive", "neutral"]:
            continue
        elif severity == "high":
            weight = 0.35
        elif severity == "medium":
            weight = 0.25
        elif severity == "low":
            weight = 0.10
        else:
            weight = 0.15

        cat_key = span.category.lower()
        if cat_key in cat_raw_sums:
            cat_raw_sums[cat_key] += weight
        else:
            cat_raw_sums["gender"] += weight

    # Apply per-category sub-score cap (0.40)
    cat_capped_scores = {c: min(0.40, sum_val) for c, sum_val in cat_raw_sums.items()}
    active_cats = [c for c, score in cat_capped_scores.items() if score > 0.0]
    num_active = len(active_cats)

    if num_active == 0:
        return 0.0

    sum_capped = sum(cat_capped_scores.values())

    if num_active == 1:
        final_score = sum_capped
    elif num_active == 2:
        final_score = (sum_capped * 1.25) + 0.10
    else:  # num_active == 3
        final_score = (sum_capped * 1.50) + 0.15

    return min(1.0, round(final_score, 2))


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

    lexicon_hits = search("bias_lexicon", body.job_description, k=10)
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
            sev = meta.get("severity", "").lower()
            if not sev:
                if any(kw in span_clean for kw in INCLUSIVE_KEYWORDS):
                    sev = "inclusive"
                elif any(kw in span_clean for kw in NEUTRAL_KEYWORDS):
                    sev = "neutral"

            if sev == "inclusive":
                observations.append(
                    f"Inclusive term '{span.text}' noted under observations. Note: Inclusive phrasing is not a defect and does not affect the risk score."
                )
            elif sev == "neutral":
                observations.append(
                    f"Standard requirement term '{span.text}' noted under observations without score impact."
                )
        else:
            dropped_count += 1
            logger.warning(f"Dropping non-verbatim bias span: '{span.text}' (not found in input text)")

    if dropped_count > 0:
        increment_dropped_bias_spans(dropped_count)

    # Post-process categories: If all matching spans for a category are severity "inclusive" or "neutral", set detected = False
    for cat in llm_res.categories:
        cat_spans = [s for s in valid_spans if s.category.lower() == cat.bias_type.lower()]
        non_info_spans = []
        for s in cat_spans:
            s_clean = s.text.strip().lower()
            sev = retrieved_lexicon_map.get(s_clean, {}).get("severity", "").lower()
            if not sev:
                if any(kw in s_clean for kw in INCLUSIVE_KEYWORDS):
                    sev = "inclusive"
                elif any(kw in s_clean for kw in NEUTRAL_KEYWORDS):
                    sev = "neutral"
            if sev not in ["info", "inclusive", "neutral"]:
                non_info_spans.append(s)

        if cat_spans and not non_info_spans:
            cat.detected = False
            cat.confidence = 0.0
            cat.suggestion = "Inclusive/standard phrasing detected; noted under observations without score defect."
        elif not cat_spans:
            cat.detected = False
            cat.confidence = 0.0

    llm_res.spans = valid_spans
    llm_res.observations = list(dict.fromkeys(observations))  # Deduplicate observations
    llm_res.overall_bias_score = compute_deterministic_bias_score(valid_spans, retrieved_lexicon_map)

    logger.info(f"/api/bias successfully audited request using serving model '{ACTIVE_MODEL_NAME}'.")
    response_cache.set(cache_payload, llm_res.model_dump())

    return llm_res

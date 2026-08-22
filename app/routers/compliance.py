import logging
import re
from typing import List, Set, Dict
from fastapi import APIRouter, Request
from app.guards import limiter, validate_text_length, response_cache, increment_dropped_compliance_violations
from app.schemas import ComplianceRequest, ComplianceResponse, Violation
from app.retrieval import search
from app.llm import complete

logger = logging.getLogger("governance_api.routers.compliance")
router = APIRouter(prefix="/api", tags=["compliance"])

MIN_SIMILARITY_SCORE = 0.25

SYSTEM_PROMPT = """You are an official EU AI Act compliance auditor evaluating AI systems against regulatory mandates.

Regulatory Article Mapping:
- Human oversight violations -> cite Article 14
- Non-discrimination or Data governance / bias violations -> cite Article 10
- Transparency violations -> cite Article 13
- Accuracy and robustness violations -> cite Article 15
- Technical documentation violations -> cite Article 11

Rules:
- Cite ONLY article numbers present in the retrieved EU AI Act reference passages (e.g., 'Article 14', 'Article 10').
- For each violation, specify principle, severity (high|medium|low), article_reference (e.g. 'Article 14'), description, action, and source excerpt.
- Two distinct violations must NOT cite the same article unless they genuinely address the same regulatory mandate.
"""


def extract_article_numbers(text_or_meta: str) -> List[str]:
    """Extracts clean article identifier strings, e.g. '14', '13', '10'."""
    s = str(text_or_meta).lower()
    matches = re.findall(r"(?:article|art\.?)\s*(\d+)", s)
    if not matches:
        matches = re.findall(r"\b(\d+)\b", s)
    return [m for m in matches if m.isdigit()]


def compute_deterministic_compliance_score(violations: List[Violation]) -> float:
    if not violations:
        return 100.0

    has_high = any(v.severity.lower() == "high" for v in violations)
    
    if has_high:
        high_count = sum(1 for v in violations if v.severity.lower() == "high")
        other_deductions = sum(15.0 if v.severity.lower() == "medium" else 5.0 for v in violations if v.severity.lower() != "high")
        base_score = 40.0 - ((high_count - 1) * 15.0) - other_deductions
        return max(0.0, round(base_score, 1))
    else:
        deductions = sum(20.0 if v.severity.lower() == "medium" else 10.0 for v in violations)
        return max(0.0, round(min(49.0, 100.0 - deductions), 1))


@router.post("/compliance", response_model=ComplianceResponse)
@limiter.limit("5/hour")
async def check_compliance(request: Request, body: ComplianceRequest) -> ComplianceResponse:
    validate_text_length(body.content)
    if body.context:
        validate_text_length(body.context)

    cache_payload = {
        "endpoint": "compliance",
        "content": body.content,
        "context": body.context or ""
    }
    cached_res = response_cache.get(cache_payload)
    if cached_res is not None:
        logger.info("Cache hit for /api/compliance request.")
        return ComplianceResponse(**cached_res)

    query_text = f"{body.content} {body.context or ''}".strip()
    dense_hits = search("eu_ai_act", query_text, k=20)
    h1 = search("eu_ai_act", "Article 14 Human oversight natural persons", k=5)
    h2 = search("eu_ai_act", "Article 10 Data governance training testing bias", k=5)

    # Deduplicate hits by text snippet while filtering by similarity floor
    all_hits_map = {}
    for h in h1 + h2 + dense_hits:
        if h.get("score", 0.0) >= MIN_SIMILARITY_SCORE and h["text"] not in all_hits_map:
            all_hits_map[h["text"]] = h

    valid_hits = list(all_hits_map.values())

    # Build exact map: article_number_string -> chunk passage text
    article_chunk_map: Dict[str, str] = {}
    chunk_passages_formatted = []

    for h in valid_hits:
        meta = h.get("meta") or h.get("metadata") or {}
        art_meta = str(meta.get("article", "")).strip()
        chunk_text = h.get("text", "").strip()
        score = h.get("score", 0.0)

        extracted_nums = []
        if art_meta:
            extracted_nums.extend(extract_article_numbers(art_meta))
        if meta.get("title"):
            extracted_nums.extend(extract_article_numbers(meta.get("title")))
        extracted_nums.extend(extract_article_numbers(chunk_text[:100]))

        for num_str in set(extracted_nums):
            if num_str not in article_chunk_map:
                article_chunk_map[num_str] = chunk_text

        art_display = f"Article {art_meta}" if art_meta.isdigit() else (art_meta or "General Provision")
        chunk_passages_formatted.append(f"[{art_display}: {meta.get('title', '')} (Score: {score:.4f})]\n{chunk_text}")

    user_prompt = f"""Retrieved EU AI Act Passages:
{chr(10).join(chunk_passages_formatted)}

AI System Description to Evaluate:
\"\"\"
Content: {body.content}
Context: {body.context or 'N/A'}
\"\"\"
"""

    llm_res: ComplianceResponse = await complete(SYSTEM_PROMPT, user_prompt, ComplianceResponse)

    valid_violations: List[Violation] = []
    seen_sources: Set[str] = set()
    dropped_count = 0

    for viol in llm_res.violations:
        cited_nums = extract_article_numbers(viol.article_reference)
        matched_num = None
        matched_chunk_text = None

        # Exact match check: Does any cited article number exist in article_chunk_map?
        for num in cited_nums:
            if num in article_chunk_map:
                matched_num = num
                matched_chunk_text = article_chunk_map[num]
                break

        if matched_chunk_text is not None and matched_num is not None:
            viol.article_reference = f"Article {matched_num}"
            viol.source = matched_chunk_text
            valid_violations.append(viol)
            seen_sources.add(matched_chunk_text)
        else:
            dropped_count += 1
            logger.warning(
                f"Dropping fabricated or un-retrieved article violation: '{viol.principle}' citing '{viol.article_reference}'"
            )

    if dropped_count > 0:
        increment_dropped_compliance_violations(dropped_count)

    llm_res.violations = valid_violations
    llm_res.compliant = len(valid_violations) == 0
    llm_res.score = compute_deterministic_compliance_score(valid_violations)

    response_cache.set(cache_payload, llm_res.model_dump())

    return llm_res

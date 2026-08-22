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

SYSTEM_PROMPT = """You are an official EU AI Act compliance auditor evaluating AI systems against regulatory mandates.
Principles:
1. Transparency (Article 13)
2. Human oversight (Article 14)
3. Accuracy and robustness (Article 15)
4. Non-discrimination (Article 10)
5. Privacy and data governance (Article 10)
6. Accountability and technical documentation (Article 11)

Rules:
- Cite ONLY article numbers that appear in the retrieved EU AI Act source text chunks (e.g., 'Article 14').
- For each violation, specify principle, severity (high|medium|low), article_reference, description, action, and brief source excerpt.
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
    act_hits = search("eu_ai_act", query_text, k=5)

    # Build exact map: article_number_string -> chunk passage text
    # e.g., '14' -> Article 14 chunk text
    article_chunk_map: Dict[str, str] = {}
    chunk_passages_formatted = []

    for h in act_hits:
        meta = h.get("meta", {})
        art_meta = str(meta.get("article", "")).strip().lower()
        chunk_text = h.get("text", "")

        # Extract article number digits from meta.article or meta.title
        extracted_nums = extract_article_numbers(art_meta)
        if not extracted_nums and meta.get("title"):
            extracted_nums = extract_article_numbers(meta.get("title"))

        for num_str in extracted_nums:
            article_chunk_map[num_str] = chunk_text

        art_display = f"Article {art_meta}" if art_meta.isdigit() else art_meta
        chunk_passages_formatted.append(f"[{art_display} - {meta.get('title', '')}]\n{chunk_text}")

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
    dropped_count = 0

    for viol in llm_res.violations:
        cited_nums = extract_article_numbers(viol.article_reference)
        matched_chunk_text = None

        # Exact match check: Does any cited article number exist in article_chunk_map?
        for num in cited_nums:
            if num in article_chunk_map:
                matched_chunk_text = article_chunk_map[num]
                break

        if matched_chunk_text is not None:
            # Enforce exact citation-source grounding: source MUST be the text of the chunk whose meta.article matched!
            viol.source = matched_chunk_text
            valid_violations.append(viol)
        else:
            dropped_count += 1
            logger.warning(
                f"Dropping fabricated article violation: '{viol.principle}' citing un-retrieved '{viol.article_reference}'"
            )

    if dropped_count > 0:
        increment_dropped_compliance_violations(dropped_count)

    llm_res.violations = valid_violations
    llm_res.compliant = len(valid_violations) == 0
    llm_res.score = compute_deterministic_compliance_score(valid_violations)

    response_cache.set(cache_payload, llm_res.model_dump())

    return llm_res

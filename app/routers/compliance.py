import logging
import re
from typing import List, Set
from fastapi import APIRouter, Request
from app.guards import limiter, validate_text_length, response_cache, increment_dropped_compliance_violations
from app.schemas import ComplianceRequest, ComplianceResponse, Violation
from app.retrieval import search
from app.llm import complete

logger = logging.getLogger("governance_api.routers.compliance")
router = APIRouter(prefix="/api", tags=["compliance"])

SYSTEM_PROMPT = """You are an official EU AI Act compliance auditor evaluating AI systems against regulatory mandates.
Principles to evaluate:
1. Transparency (Article 13)
2. Human oversight (Article 14)
3. Accuracy and robustness (Article 15)
4. Non-discrimination (Article 10)
5. Privacy and data governance (Article 10)
6. Accountability and technical documentation (Article 11)

Rules:
- Cite ONLY articles that appear in the retrieved EU AI Act source text chunks.
- For each violation, specify principle, severity (high|medium|low), article_reference (e.g. 'Article 14'), description, action, and source text.
"""


def extract_article_ids(text_or_meta: str) -> Set[str]:
    """Extracts article identifiers (e.g. '14', '10', 'annex iii') from string/meta."""
    found = set()
    s = str(text_or_meta).lower()
    matches = re.findall(r"(?:article|art\.?)\s*(\d+)", s)
    for m in matches:
        found.add(m)
    annexes = re.findall(r"(?:annex)\s*([i|v|x\d]+)", s)
    for a in annexes:
        found.add(f"annex {a}")
    return found


@router.post("/compliance", response_model=ComplianceResponse)
@limiter.limit("5/hour")
async def check_compliance(request: Request, body: ComplianceRequest) -> ComplianceResponse:
    validate_text_length(body.content)
    if body.context:
        validate_text_length(body.context)

    # Check cache first
    cache_payload = {
        "endpoint": "compliance",
        "content": body.content,
        "context": body.context or ""
    }
    cached_res = response_cache.get(cache_payload)
    if cached_res is not None:
        logger.info("Cache hit for /api/compliance request.")
        return ComplianceResponse(**cached_res)

    # Retrieve top 8 eu_ai_act chunks
    query_text = f"{body.content} {body.context or ''}".strip()
    act_hits = search("eu_ai_act", query_text, k=8)

    allowed_article_ids: Set[str] = set()
    chunk_passages = []

    for h in act_hits:
        m = h.get("meta", {})
        art = m.get("article")
        if art is not None:
            allowed_article_ids.add(str(art).lower())
            allowed_article_ids.update(extract_article_ids(str(art)))
        
        title = m.get("title", "")
        allowed_article_ids.update(extract_article_ids(title))
        
        chunk_passages.append({
            "article": f"Article {art}" if str(art).isdigit() else str(art),
            "title": title,
            "text": h.get("text", "")
        })

    retrieved_sources_formatted = []
    for cp in chunk_passages:
        retrieved_sources_formatted.append(
            f"[{cp['article']} - {cp['title']}]\n{cp['text']}"
        )

    user_prompt = f"""Retrieved EU AI Act Passages:
{chr(10).join(retrieved_sources_formatted)}

AI System Description to Evaluate:
\"\"\"
Content: {body.content}
Context: {body.context or 'N/A'}
\"\"\"
"""

    # Call LLM
    llm_res: ComplianceResponse = await complete(SYSTEM_PROMPT, user_prompt, ComplianceResponse)

    # Server-Side Citation Validation & Violation Dropping
    valid_violations: List[Violation] = []
    dropped_count = 0

    for viol in llm_res.violations:
        cited_ids = extract_article_ids(viol.article_reference)
        # Verify if cited article ID exists in the allowed retrieved set
        is_allowed = False
        if not cited_ids:
            # If no article number extracted, check direct string presence
            is_allowed = any(str(a) in viol.article_reference.lower() for a in allowed_article_ids)
        else:
            is_allowed = bool(cited_ids.intersection(allowed_article_ids))

        if is_allowed:
            # Match actual retrieved chunk text to populate violation.source
            best_source = chunk_passages[0]["text"] if chunk_passages else viol.source
            for cp in chunk_passages:
                if any(cid in cp["article"].lower() for cid in cited_ids):
                    best_source = cp["text"]
                    break
            viol.source = best_source
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

    # Calculate deterministic score
    deductions = sum(30.0 if v.severity.lower() == "high" else 15.0 for v in valid_violations)
    llm_res.score = max(0.0, round(100.0 - deductions, 1))

    # Store in response_cache
    response_cache.set(cache_payload, llm_res.model_dump())

    return llm_res

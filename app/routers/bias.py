from fastapi import APIRouter, Request
from app.guards import limiter, validate_text_length
from app.schemas import BiasRequest, BiasResponse, BiasSpan, CategoryFinding

router = APIRouter(prefix="/api", tags=["bias"])

SAMPLE_BIAS_RESPONSE = BiasResponse(
    overall_bias_score=0.92,
    spans=[
        BiasSpan(text="young, energetic salesman", category="gender"),
        BiasSpan(text="10+ years experience", category="age"),
        BiasSpan(text="cultural fit for our Western team", category="cultural"),
        BiasSpan(text="rockstar", category="gender"),
    ],
    categories=[
        CategoryFinding(
            bias_type="gender",
            detected=True,
            confidence=0.85,
            examples=["salesman", "he", "rockstar", "crush targets"],
            suggestion="Replace gendered titles and pronouns with neutral equivalents, and swap aggressive masculine-coded verbs for plain descriptions of the work."
        ),
        CategoryFinding(
            bias_type="age",
            detected=True,
            confidence=0.96,
            examples=["young", "energetic", "10+ years"],
            suggestion="Remove youth-coded adjectives and re-check whether the years requirement is genuinely essential at this level."
        ),
        CategoryFinding(
            bias_type="cultural",
            detected=True,
            confidence=0.94,
            examples=["Western team", "cultural fit"],
            suggestion="Replace subjective cultural criteria with objective competencies and stated company values."
        )
    ],
    summary="Flagged bias across 3 categories. Revisions recommended before publishing."
)


@router.post("/bias", response_model=BiasResponse)
@limiter.limit("5/hour")
async def audit_bias(request: Request, body: BiasRequest) -> BiasResponse:
    validate_text_length(body.job_description)
    return SAMPLE_BIAS_RESPONSE

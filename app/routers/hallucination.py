from fastapi import APIRouter, Request
from app.guards import limiter, clamp_num_questions
from app.schemas import HallucinationRequest, HallucinationResponse, HallucinationQueryResult

router = APIRouter(prefix="/api", tags=["hallucination"])

SAMPLE_HALLUCINATION_RESPONSE = HallucinationResponse(
    topic="Discovery of Radium",
    questions_tested=3,
    hallucination_rate=0.33,
    results=[
        HallucinationQueryResult(
            question="Who discovered radium?",
            answer="Marie and Pierre Curie discovered radium.",
            verdict="ACCURATE",
            confidence=1.0,
            reasoning="Matches the retrieved passage directly.",
            source="Radium was discovered in 1898 by Marie and Pierre Curie, who extracted it from pitchblende residues."
        ),
        HallucinationQueryResult(
            question="In what year was radium isolated in pure metallic form?",
            answer="1902, by Marie Curie alone.",
            verdict="HALLUCINATED",
            confidence=0.9,
            reasoning="The retrieved passage gives 1910 and names two people. 1902 was the year radium chloride was isolated, not the metal.",
            source="Pure metallic radium was first isolated in 1910 by Marie Curie and André-Louis Debierne through electrolysis."
        ),
        HallucinationQueryResult(
            question="What element was discovered alongside radium?",
            answer="Polonium, earlier the same year.",
            verdict="ACCURATE",
            confidence=0.95,
            reasoning="Consistent with the retrieved passage.",
            source="The Curies announced polonium in July 1898 and radium in December of the same year."
        )
    ]
)


@router.post("/hallucination", response_model=HallucinationResponse)
@limiter.limit("5/hour")
async def test_hallucination(request: Request, body: HallucinationRequest) -> HallucinationResponse:
    num_questions = clamp_num_questions(body.num_questions)
    res = SAMPLE_HALLUCINATION_RESPONSE.model_copy()
    res.topic = body.topic
    res.questions_tested = num_questions
    res.results = res.results[:num_questions]
    return res

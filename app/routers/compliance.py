from fastapi import APIRouter, Request
from app.guards import limiter, validate_text_length
from app.schemas import ComplianceRequest, ComplianceResponse, Violation

router = APIRouter(prefix="/api", tags=["compliance"])

SAMPLE_COMPLIANCE_RESPONSE = ComplianceResponse(
    compliant=False,
    score=50.0,
    summary="The described lending system breaches core EU AI Act requirements. Automatic denial without human review conflicts with Article 14, and postal code as a decision input creates proxy discrimination risk under Article 10.",
    violations=[
        Violation(
            principle="Human oversight",
            severity="high",
            article_reference="Art. 14",
            description="Fully automated credit denial with no human review or appeal path fails oversight requirements for high-risk systems.",
            action="Add a mandatory human review step before any final rejection is issued.",
            source="High-risk AI systems shall be designed and developed in such a way that they can be effectively overseen by natural persons during the period in which they are in use."
        ),
        Violation(
            principle="Non-discrimination",
            severity="high",
            article_reference="Art. 10",
            description="Postal code is a documented proxy for race and income, producing indirect discriminatory impact.",
            action="Drop geographic features from decision inputs and run demographic parity tests on the remainder.",
            source="Training, validation and testing data sets shall be subject to data governance appropriate to the intended purpose, including examination in view of possible biases."
        )
    ]
)


@router.post("/compliance", response_model=ComplianceResponse)
@limiter.limit("5/hour")
async def check_compliance(request: Request, body: ComplianceRequest) -> ComplianceResponse:
    validate_text_length(body.content)
    if body.context:
        validate_text_length(body.context)
    return SAMPLE_COMPLIANCE_RESPONSE

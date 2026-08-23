from typing import List, Optional
from pydantic import BaseModel, Field


# --- Bias Schemas ---
class BiasRequest(BaseModel):
    job_description: str = Field(..., max_length=2000, description="The job posting text to audit.")
    analysis_type: Optional[List[str]] = Field(
        default=["gender", "age", "cultural"],
        description="Bias categories to audit."
    )


class BiasSpan(BaseModel):
    text: str
    category: str  # gender | age | cultural


class CategoryFinding(BaseModel):
    bias_type: str
    detected: bool
    confidence: float
    examples: List[str]
    suggestion: str


class BiasResponse(BaseModel):
    overall_bias_score: float
    spans: List[BiasSpan]
    categories: List[CategoryFinding]
    summary: str
    observations: List[str] = Field(default_factory=list, description="Inclusive/neutral phrasing observations.")



# --- Compliance Schemas ---
class ComplianceRequest(BaseModel):
    content: str = Field(..., max_length=2000, description="Description of the AI system or feature.")
    context: Optional[str] = Field(default="", max_length=500, description="Optional context.")


class Violation(BaseModel):
    principle: str
    severity: str
    article_reference: str
    description: str
    action: str
    source: str


class ComplianceResponse(BaseModel):
    compliant: bool
    score: float
    summary: str
    violations: List[Violation]


# --- Hallucination Schemas ---
class HallucinationRequest(BaseModel):
    topic: str = Field(..., description="Topic to test for hallucinations.")
    num_questions: int = Field(default=2, ge=1, le=3, description="Number of questions (1-3).")


class HallucinationQueryResult(BaseModel):
    question: str
    answer: str
    verdict: str  # ACCURATE | HALLUCINATED | UNCERTAIN
    confidence: float
    reasoning: str
    source: str


class HallucinationResponse(BaseModel):
    topic: str
    questions_tested: int
    hallucination_rate: float
    results: List[HallucinationQueryResult]

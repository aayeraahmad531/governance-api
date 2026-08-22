import pytest
import os
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

POSTING_1_SENIOR_ENGINEER = (
    "We are seeking an experienced Senior Software Engineer to join our collaborative backend team. "
    "In this role, you will design, build, and maintain high-throughput distributed microservices using Python and PostgreSQL. "
    "You will work closely with cross-functional product, data, and frontend engineers to deliver reliable customer features. "
    "Requirements include at least 5 years of experience in software development, strong proficiency in RESTful API design, "
    "and excellent written and verbal communication skills. We operate in an agile, fast-paced environment where continuous "
    "improvement and teamwork are valued. We offer competitive compensation, health benefits, and flexible remote working."
)

POSTING_2_PRODUCT_MARKETING = (
    "Our growing SaaS platform is looking for an experienced Product Marketing Manager to lead go-to-market strategies "
    "and product messaging. Working within a collaborative marketing team, you will translate complex technical features into "
    "compelling customer value propositions. Responsibilities include conducting user research, crafting product positioning "
    "guides, and coordinating product launches alongside sales and product teams. The ideal candidate brings 5 years of experience "
    "in B2B technology marketing, a data-driven mindset, and outstanding communication skills. If you thrive in a fast-paced environment "
    "and enjoy cross-functional project management, we welcome your application."
)

POSTING_3_FINANCIAL_ANALYST = (
    "We are hiring a Senior Financial Analyst to support strategic corporate planning and financial modeling. "
    "As a key member of our finance team, you will prepare quarterly financial forecasts, analyze operational performance metrics, "
    "and present actionable insights to executive leadership. Candidates must possess at least 5 years of experience in financial "
    "analysis or corporate finance, advanced proficiency in Excel, and strong communication skills to convey complex financial "
    "data to non-finance stakeholders. Our team fosters a collaborative culture focused on professional growth. We provide flexible "
    "hybrid work options, comprehensive medical benefits, and 401k matching."
)

POSTING_4_CUSTOMER_SUCCESS = (
    "Join our customer support department as a Customer Success Specialist dedicated to delivering exceptional user experiences. "
    "You will manage customer onboarding, troubleshoot technical inquiries, and ensure high customer satisfaction across our client base. "
    "Working closely with product and engineering teams, you will act as an advocate for client feedback to drive product enhancements. "
    "Required qualifications include 3 to 5 years of experience in client-facing technology support, strong problem-solving abilities, "
    "and interpersonal communication skills. We offer a supportive, team-oriented culture in a fast-paced environment with opportunities "
    "for career advancement and flexible working hours."
)

POSTING_5_OPERATIONS_LEAD = (
    "We are seeking a detail-oriented Operations Lead to streamline internal business workflows and manage vendor relationships. "
    "In this role, you will optimize operational processes, track key performance indicators, and coordinate inter-departmental logistics "
    "across our organization. The successful candidate will have 5 years of experience in business operations or project coordination, "
    "proven analytical capabilities, and strong verbal and written communication skills. You will thrive in a collaborative, fast-paced setting "
    "alongside a dedicated team. We provide a competitive salary, comprehensive health and dental coverage, remote flexibility, and ongoing "
    "professional development opportunities."
)

TEST_POSTINGS = [
    ("Senior Software Engineer", POSTING_1_SENIOR_ENGINEER),
    ("Product Marketing Manager", POSTING_2_PRODUCT_MARKETING),
    ("Senior Financial Analyst", POSTING_3_FINANCIAL_ANALYST),
    ("Customer Success Specialist", POSTING_4_CUSTOMER_SUCCESS),
    ("Operations Lead", POSTING_5_OPERATIONS_LEAD)
]


@pytest.mark.live
@pytest.mark.parametrize("title,posting_text", TEST_POSTINGS)
def test_false_positive_low_bias_score(title: str, posting_text: str):
    """
    False-Positive Test Suite (Runs against live LLM via `pytest -m live`).
    Verifies that legitimate, well-written job postings score LOW on overall_bias_score (< 0.25)
    and return no detected high-confidence bias categories (> 0.5).
    """
    api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY is not set. Populate GEMINI_API_KEY in .env to run live false-positive tests.")

    body = {
        "job_description": posting_text,
        "analysis_type": ["gender", "age", "cultural"]
    }
    
    response = client.post("/api/bias", json=body)
    assert response.status_code == 200, f"API returned status {response.status_code}: {response.text}"
    
    data = response.json()
    score = data.get("overall_bias_score", 0.0)
    categories = data.get("categories", [])
    
    print(f"\n--- LIVE FALSE-POSITIVE REPORT: '{title}' ---")
    print(f"Overall Bias Score: {score}")
    print(f"Detected Spans ({len(data.get('spans', []))}): {[s['text'] for s in data.get('spans', [])]}")
    for cat in categories:
        print(f"  Category '{cat['bias_type']}': detected={cat['detected']}, confidence={cat['confidence']}")

    # ASSERTION 1: overall_bias_score must be strictly less than 0.25
    assert score < 0.25, f"False Positive! '{title}' scored {score} >= 0.25 threshold!"

    # ASSERTION 2: All bias categories must be detected == False for clean postings
    for cat in categories:
        assert cat.get("detected") is False, f"False Positive! Category '{cat['bias_type']}' flagged detected=True in clean posting '{title}'!"


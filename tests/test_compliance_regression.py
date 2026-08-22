import pytest
import os
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

POSTAL_CODE_CREDIT_REJECTION_INPUT = {
    "content": "Our AI model automatically rejects credit applications for applicants living in specific postal codes without human intervention.",
    "context": "Fintech automated lending system"
}


@pytest.mark.live
def test_compliance_cites_correct_articles():
    """
    Live Regression Test:
    Verifies that credit rejection based on postal codes without human intervention
    cites Article 10 and/or Article 14, and does NOT cite Article 95.
    Also verifies each violation carries its grounded legal reference passage as source.
    """
    api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY is not set.")

    res = client.post("/api/compliance", json=POSTAL_CODE_CREDIT_REJECTION_INPUT)
    assert res.status_code == 200, f"API returned status {res.status_code}: {res.text}"

    data = res.json()
    assert data["compliant"] is False, f"Expected compliant=False, got {data['compliant']}"
    assert data["score"] < 50.0, f"Expected non-compliant score < 50, got {data['score']}"

    violations = data.get("violations", [])
    assert len(violations) > 0, "Expected at least 1 violation for non-compliant input."

    cited_articles = [v["article_reference"].lower() for v in violations]
    sources = [v["source"] for v in violations]

    print("\n--- LIVE COMPLIANCE CITATION REGRESSION TEST ---")
    print(f"Compliant: {data['compliant']}, Score: {data['score']}")
    for idx, v in enumerate(violations, 1):
        print(f"Violation {idx}: principle='{v['principle']}', article='{v['article_reference']}'")
        print(f"  Source excerpt: {v['source'][:100]}...")

    # ASSERTION 1: Must NOT cite Article 95
    for art in cited_articles:
        assert "95" not in art, f"Regression! Violation cited Article 95: {art}"

    # ASSERTION 2: Must cite Article 10 or Article 14
    has_art_10_or_14 = any("10" in art or "14" in art for art in cited_articles)
    assert has_art_10_or_14, f"Regression! Expected citation of Article 10 or 14, got {cited_articles}"

    # ASSERTION 3: Source passages must be retrieved legal text, not user input text
    user_text = POSTAL_CODE_CREDIT_REJECTION_INPUT["content"].lower()
    for src in sources:
        assert len(src) > 50, "Source snippet is too short or empty."
        assert user_text not in src.lower(), "Source snippet contains user input text instead of retrieved legal passage."

    # ASSERTION 4: Violations citing distinct articles must carry distinct source passages
    if len(violations) >= 2:
        arts = [v["article_reference"] for v in violations]
        if len(set(arts)) > 1:
            assert len(set(sources)) > 1, f"Violations citing different articles ({arts}) shared identical source passage!"


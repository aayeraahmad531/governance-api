import pytest
from app.retrieval import search


def test_eu_ai_act_search_article_14():
    results = search("eu_ai_act", "automated decision without human review", k=5)
    assert len(results) > 0
    top_result = results[0]
    assert top_result["meta"]["article"] == 14
    assert "human oversight" in top_result["meta"]["title"].lower()
    assert top_result["meta"]["source_version"] == "02024R1689-20260727"


def test_bias_lexicon_search():
    results = search("bias_lexicon", "young energetic salesman", k=3)
    assert len(results) > 0
    categories = [r["meta"].get("category") for r in results]
    assert any(c in ["gender", "age"] for c in categories)


def test_facts_search_radium():
    results = search("facts", "Who discovered radium?", k=3)
    assert len(results) > 0
    assert any("Curie" in r["text"] for r in results)


def test_missing_index_returns_empty():
    results = search("non_existent_index", "test query")
    assert results == []

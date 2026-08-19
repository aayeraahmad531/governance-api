import pytest
from app.retrieval import search, INDEXES


def test_corpus_sizes():
    assert "eu_ai_act" in INDEXES
    assert "bias_lexicon" in INDEXES
    assert "facts" in INDEXES
    
    assert len(INDEXES["eu_ai_act"]["chunks"]) >= 300
    assert len(INDEXES["bias_lexicon"]["chunks"]) >= 80
    assert len(INDEXES["facts"]["chunks"]) >= 75


def test_eu_ai_act_search_article_14():
    results = search("eu_ai_act", "automated decision without human review", k=5)
    assert len(results) > 0
    top_articles = [r["meta"].get("article") for r in results]
    assert 14 in top_articles
    
    # Verify snippets never cut mid-word or start with lowercase fragments
    for r in results:
        text = r["text"]
        assert not text.startswith("hat ")
        assert text[0].isupper() or text[0].isdigit() or text[0] in ['"', "'", "‘"]


def test_bias_lexicon_expanded_categories():
    results_masculine = search("bias_lexicon", "ninja rockstar aggressive coding developer", k=5)
    assert any(r["meta"].get("category") == "gender" for r in results_masculine)

    results_age = search("bias_lexicon", "young energetic digital native recent graduate", k=5)
    assert any(r["meta"].get("category") == "age" for r in results_age)

    results_cultural = search("bias_lexicon", "cultural fit native speaker Western team", k=5)
    assert any(r["meta"].get("category") == "cultural" for r in results_cultural)


def test_facts_substantive_topics():
    topics = [
        ("Who discovered radium?", "Curie"),
        ("What date did Apollo 11 land on the Moon?", "July"),
        ("Human oversight requirements under Article 14 of the EU AI Act", "human oversight"),
        ("What enzyme fixes carbon dioxide in photosynthesis?", "RuBisCO"),
        ("Who founded ISRO?", "Sarabhai")
    ]
    for query, expected_keyword in topics:
        results = search("facts", query, k=5)
        assert len(results) > 0
        assert any(expected_keyword.lower() in r["text"].lower() for r in results)


def test_missing_index_returns_empty():
    results = search("non_existent_index", "test query")
    assert results == []

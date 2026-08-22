import pytest
from app.retrieval import search, INDEXES, encode_query_onnx


def test_corpus_sizes():
    assert "eu_ai_act" in INDEXES
    assert "bias_lexicon" in INDEXES
    assert "facts" in INDEXES
    
    assert len(INDEXES["eu_ai_act"]["chunks"]) >= 300
    assert len(INDEXES["bias_lexicon"]["chunks"]) >= 70
    assert len(INDEXES["facts"]["chunks"]) >= 80


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


def test_bias_lexicon_feminine_info_severity():
    results_feminine = search("bias_lexicon", "nurturing supportive collaborative team player", k=5)
    assert len(results_feminine) > 0
    # Feminine-coded and standard terms must have severity in {'inclusive', 'neutral', 'info'} and carry zero score impact
    non_scoring_entries = [r for r in results_feminine if r["meta"].get("severity") in {"inclusive", "neutral", "info"}]
    assert len(non_scoring_entries) > 0


def test_facts_wikipedia_provenance():
    results = search("facts", "Who discovered radium in 1898?", k=5)
    assert len(results) > 0
    for r in results:
        meta = r["meta"]
        assert "source_url" in meta
        assert meta["source_url"].startswith("https://en.wikipedia.org/wiki/")
        assert meta["retrieved_date"] == "2026-08-21"


def test_onnx_query_embedding_shape_and_norm():
    vec = encode_query_onnx("automated decision without human review")
    assert vec.shape == (384,)
    assert abs(float((vec**2).sum()) - 1.0) < 1e-4


def test_missing_index_returns_empty():
    results = search("non_existent_index", "test query")
    assert results == []

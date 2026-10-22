"""Offline tests (no network, no API key). Run: python -m pytest -q"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.analyzer import normalize_verdict, _finalize, _base_result  # noqa: E402
from services.article import ArticleError, _check_url  # noqa: E402
from services.sources import classify_source  # noqa: E402
from services.text_utils import (  # noqa: E402
    detect_language, is_only_url, known_fact_hints, question_to_claim, writing_signals,
)


def test_language_detection():
    assert detect_language("India won the World Cup") == "english"
    assert detect_language("500 ke note band ho jayenge") == "hinglish"
    assert detect_language("भारत की राजधानी नई दिल्ली है") == "hindi"


def test_question_to_claim():
    assert question_to_claim("Is Salman Khan dead?") == "Salman Khan is dead."


def test_known_facts_do_not_fire_on_unrelated_numbers():
    assert known_fact_hints("300 workers died in the first factory fire") == known_fact_hints("workers died")
    assert any("₹300" in h for h in known_fact_hints("RBI launched a new Rs 300 note"))
    assert any("₹500" in h for h in known_fact_hints("500 ke note band ho jayenge"))
    assert not any("₹500" in h for h in known_fact_hints("My husband has broadband"))


def test_writing_signals():
    sig = writing_signals("FORWARD THIS TO EVERYONE NOW!!! MEDIA WON'T SHOW THIS", "english")
    assert "Asks you to forward or share it" in sig
    assert writing_signals("The Reserve Bank released its annual report.") == []


def test_verdict_normalisation():
    assert normalize_verdict("Partially True") == "Partially Fake"
    assert normalize_verdict("Not true") == "Fake"
    assert normalize_verdict("Mostly accurate") == "Real"
    assert normalize_verdict("???") == "Unverifiable"


def test_finalize_clamps_scores_and_marks_cited_sources():
    evidence = [{"title": "A", "url": "https://x", "source": "X", "type": "major"},
                {"title": "B", "url": "https://y", "source": "Y", "type": "factcheck"}]
    out = _finalize({"verdict": "Fake", "score": 95, "cited": [2]}, _base_result("english"), evidence)
    assert out["verdict"] == "False" and out["score"] <= 30
    assert [s["cited"] for s in out["sources"]] == [False, True]


def test_source_classification():
    assert classify_source("https://www.altnews.in") == "factcheck"
    assert classify_source("https://www.reuters.com", "Fact Check: viral video is fake") == "factcheck"
    assert classify_source("https://randomblog.example", "Fact check: this is fake") == "other"


def test_link_safety():
    assert is_only_url("https://example.com/news")
    for bad in ("http://127.0.0.1/admin", "http://169.254.169.254/", "ftp://example.com/x", "http://example.com:8080/"):
        try:
            _check_url(bad)
        except ArticleError:
            continue
        raise AssertionError(f"{bad} should be blocked")

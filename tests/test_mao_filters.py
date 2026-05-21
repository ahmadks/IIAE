"""Unit tests for Annex V lexical MAO filters (language-agnostic)."""

from iiae.mao.filters import (
    MAOFilterConfig,
    axiomatic_invariance_filter,
    concurrent_probability_filter,
    geoclimatic_synchrony_filter,
    material_causality_filter,
)


def test_material_causality_overlap():
    cfg = MAOFilterConfig(causality_threshold=0.2)
    report = material_causality_filter(
        "Paris is the capital of France.",
        "France capital city Paris Europe.",
        config=cfg,
    )
    assert report["passed"] is True
    assert report["score"] is not None


def test_axiomatic_preservation():
    cfg = MAOFilterConfig(axiom_preservation_threshold=0.5)
    report = axiomatic_invariance_filter(
        ["France capital city Paris Europe"],
        "France is in Europe and Paris is its capital.",
        config=cfg,
    )
    assert report["passed"] is True


def test_concurrent_probability_borel():
    cfg = MAOFilterConfig(borel_threshold=0.05)
    report = concurrent_probability_filter(
        "France is a country in Europe. Its capital city is Paris.",
        "France is a country in Europe. Its capital city is Paris.",
        ["France is a country in Europe. Its capital city is Paris."],
        config=cfg,
    )
    assert report["passed"] is True
    assert report["score"] is not None


def test_geoclimatic_lexical_defers_to_ml():
    report = geoclimatic_synchrony_filter("text", "context")
    assert report["passed"] is True
    assert "ML" in (report.get("reason") or "")

import pytest
from iiae.dse import extract_axioms
from iiae.dqe import deviation_score, classify_ds

def test_extract_axioms():
    context = "Rule one is simple. The second rule is longer. A."
    # min_len=10 should filter out "A."
    axioms = extract_axioms(context, min_len=10)
    
    assert len(axioms) == 2
    assert "Rule one is simple" in axioms
    assert "The second rule is longer" in axioms

def test_deviation_score_perfect():
    axioms = ["Rule one is simple"]
    response = "Rule one is simple indeed"
    ds = deviation_score(response, axioms)
    assert ds == 0.0
    assert classify_ds(ds) == "Standard-Zero"

def test_deviation_score_partial():
    axioms = ["Rule one is simple", "Another distinct requirement"]
    response = "Rule one is simple"
    # Matches 1 out of 2 -> preservation=0.5 -> ds=0.5
    ds = deviation_score(response, axioms)
    assert ds == 0.5
    assert classify_ds(ds) == "Violation"

def test_deviation_score_total_failure():
    axioms = ["Rule one is simple"]
    response = "Apples are tasty"
    ds = deviation_score(response, axioms)
    assert ds == 1.0
    assert classify_ds(ds) == "Critical"

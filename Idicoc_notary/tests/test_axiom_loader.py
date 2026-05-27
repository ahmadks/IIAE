import os
import pytest
from idicoc_notary_core.audit.graph.loader import FileAxiomLoader, InlineAxiomLoader

def test_inline_axiom_loader():
    axioms = [{"id": "ax1", "text": "Test axiom", "type": "fact"}]
    loader = InlineAxiomLoader(axioms)
    loaded = loader.load_axioms()
    assert len(loaded) == 1
    assert loaded[0]["id"] == "ax1"
    assert loaded[0]["text"] == "Test axiom"

def test_file_axiom_loader_text(tmp_path):
    file_path = tmp_path / "axioms.txt"
    file_path.write_text(
        "# Comment line\n"
        "Axiom 1 | protocol | affirmative | hard | 10\n"
        "\n"
        "Axiom 2 | fact | negative | soft\n"
        "Axiom 3\n"
    )

    loader = FileAxiomLoader(str(file_path))
    loaded = loader.load_axioms()
    
    assert len(loaded) == 3
    assert loaded[0]["text"] == "Axiom 1"
    assert loaded[0]["axiom_type"] == "protocol"
    assert loaded[0]["polarity"] == "affirmative"
    assert loaded[0]["hardness"] == "hard"
    assert loaded[0]["priority"] == 10

    assert loaded[1]["text"] == "Axiom 2"
    assert loaded[1]["axiom_type"] == "fact"
    assert loaded[1]["polarity"] == "negative"
    assert loaded[1]["hardness"] == "soft"
    assert loaded[1]["priority"] == 1

    assert loaded[2]["text"] == "Axiom 3"
    assert loaded[2]["axiom_type"] == "fact" # default
    assert loaded[2]["polarity"] == "affirmative" # default
    assert loaded[2]["hardness"] == "soft" # default

def test_file_axiom_loader_json(tmp_path):
    import json
    file_path = tmp_path / "axioms.json"
    data = [{"id": "ax1", "text": "Axiom JSON", "axiom_type": "world"}]
    file_path.write_text(json.dumps(data))

    loader = FileAxiomLoader(str(file_path))
    loaded = loader.load_axioms()
    
    assert len(loaded) == 1
    assert loaded[0]["text"] == "Axiom JSON"
    assert loaded[0]["axiom_type"] == "world"

def test_file_axiom_loader_missing_file():
    loader = FileAxiomLoader("non_existent_file.txt")
    loaded = loader.load_axioms()
    assert loaded == []

import os
import pytest
from idicoc_notary_core.audit.graph.loader import FilePolicyLoader, InlinePolicyLoader

def test_inline_policy_loader():
    policies = [{"id": "ax1", "text": "Test policy", "type": "fact"}]
    loader = InlinePolicyLoader(policies)
    loaded = loader.load_policies()
    assert len(loaded) == 1
    assert loaded[0]["id"] == "ax1"
    assert loaded[0]["text"] == "Test policy"

def test_file_policy_loader_text(tmp_path):
    file_path = tmp_path / "policies.txt"
    file_path.write_text(
        "# Comment line\n"
        "Policy 1 | protocol | affirmative | hard | 10\n"
        "\n"
        "Policy 2 | fact | negative | soft\n"
        "Policy 3\n"
    )

    loader = FilePolicyLoader(str(file_path))
    loaded = loader.load_policies()
    
    assert len(loaded) == 3
    assert loaded[0]["text"] == "Policy 1"
    assert loaded[0]["policy_type"] == "protocol"
    assert loaded[0]["polarity"] == "affirmative"
    assert loaded[0]["hardness"] == "hard"
    assert loaded[0]["priority"] == 10

    assert loaded[1]["text"] == "Policy 2"
    assert loaded[1]["policy_type"] == "fact"
    assert loaded[1]["polarity"] == "negative"
    assert loaded[1]["hardness"] == "soft"
    assert loaded[1]["priority"] == 1

    assert loaded[2]["text"] == "Policy 3"
    assert loaded[2]["policy_type"] == "fact" # default
    assert loaded[2]["polarity"] == "affirmative" # default
    assert loaded[2]["hardness"] == "soft" # default

def test_file_policy_loader_json(tmp_path):
    import json
    file_path = tmp_path / "policies.json"
    data = [{"id": "ax1", "text": "Policy JSON", "policy_type": "world"}]
    file_path.write_text(json.dumps(data))

    loader = FilePolicyLoader(str(file_path))
    loaded = loader.load_policies()
    
    assert len(loaded) == 1
    assert loaded[0]["text"] == "Policy JSON"
    assert loaded[0]["policy_type"] == "world"

def test_file_policy_loader_missing_file():
    loader = FilePolicyLoader("non_existent_file.txt")
    loaded = loader.load_policies()
    assert loaded == []

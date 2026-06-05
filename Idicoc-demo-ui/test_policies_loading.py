import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "Idicoc_notary")))

from idicoc_notary_core import AuditConfig, InlinePolicyLoader
from idicoc_notary_core.audit.wrapper_pipeline import IDICOCNotaryClient
from client_simulator import load_policies_from_file


def build_demo_notary(policies, epsilon: float = 0.20):
    return IDICOCNotaryClient(
        AuditConfig(
            instance_name="demo-notary",
            rigidity_epsilon=epsilon,
            dissonance_weights=(0.0, 0.5, 0.4, 0.1, 0.0, 0.0, 0.0),
            policy_loader=InlinePolicyLoader(policies),
            ctm_nodes_path=os.path.join(HERE, "ctm_nodes.json"),
            ctm_root_path=os.path.join(HERE, "ctm_root.txt"),
        )
    )


def test_load_policies_from_demo_file():
    policies_path = HERE / "policies.txt"
    assert (
        policies_path.exists()
    ), "El archivo policies.txt debe existir en Idicoc-demo-ui"

    policies = load_policies_from_file(str(policies_path))
    assert isinstance(policies, list), "La función debe devolver una lista"
    assert len(policies) >= 4, "Debe cargar al menos las políticas activas del archivo"

    first_policy = policies[0]
    assert first_policy["id"] == "ax_regex_1"
    assert first_policy["policy_type"] == "regex"
    assert first_policy["polarity"] == "negative"
    assert first_policy["hardness"] == "hard"
    assert first_policy["priority"] == 10
    assert first_policy["source_text"] == first_policy["text"]

    assert all(not str(p["id"]).startswith("#") for p in policies)


def test_numeric_vector_policy_accepts_first_bin_below_half():
    policies = load_policies_from_file(str(HERE / "policies.txt"))
    numeric_policies = [
        p for p in policies if p.get("mode", "all") in ("numeric", "all")
    ]
    assert any(p["id"] == "ax_regex_1" for p in numeric_policies)

    import numpy as np
    from idicoc_notary_core.audit import SemanticPayload

    notary = build_demo_notary(numeric_policies)
    lst = [0.3, 0.25, 0.2, 0.25]
    result = notary.process_interaction(
        audit_input=SemanticPayload(text="numeric signal", vec=np.array(lst), source_text=str(lst), payload_type="numeric"),
        context_input=[],
        context_policies=numeric_policies,
    )

    d2 = result.get("dissonance_metrics", {}).get("d_2", 0.0)
    assert not math.isinf(
        d2
    ), f"No se esperaba violación de d_2 para un vector válido: {d2}"
    assert result.get("status") == "ADMITTED"


def test_numeric_vector_policy_rejects_first_bin_above_half():
    policies = load_policies_from_file(str(HERE / "policies.txt"))
    numeric_policies = [
        p for p in policies if p.get("mode", "all") in ("numeric", "all")
    ]

    import numpy as np
    from idicoc_notary_core.audit import SemanticPayload

    notary = build_demo_notary(numeric_policies)
    lst = [0.6, 0.2, 0.1, 0.1]
    result = notary.process_interaction(
        audit_input=SemanticPayload(text="numeric signal", vec=np.array(lst), source_text=str(lst), payload_type="numeric"),
        context_input=[],
        context_policies=numeric_policies,
    )

    d2 = result.get("dissonance_metrics", {}).get("d_2", 0.0)
    assert math.isinf(d2), "Se esperaba d_2 infinito cuando el primer bin supera 0.5"

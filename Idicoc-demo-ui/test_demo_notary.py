import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Idicoc_notary"))
)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from idicoc_core.api.facade import NotaryClient
from idicoc_core.config import AuditConfig
from providers.phi_provider import PhiProvider


@pytest.fixture(scope="module")
def phi_notary_client():
    """Fixture que instancia el LLM y el notary UNA SOLA VEZ para todo el módulo."""
    policy_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "policies.txt")
    )
    phi_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "models_cache",
            "Phi-3.5-mini-instruct",
        )
    )
    phi_provider = PhiProvider(model_path=phi_path)
    config = AuditConfig(
        embedding_provider=phi_provider.embedding_provider,
        compile_policies_on_init=True,
        ctm_mode="memory",
        correction_base_tolerance=0.0,
        allowed_epsilon=0.0,
        policy_file_path=policy_file,
    )
    client = NotaryClient(config, llm_provider=phi_provider)
    return client, phi_provider


def test_notary_rejects_prohibited_manzana_from_demo_policies(phi_notary_client):
    """Test 1: Verifica que la palabra 'manzana' sea rechazada directamente."""
    client, _ = phi_notary_client

    output, result = client.generate(
        user_prompt="di manzana",
        rag_context="",
    )

    print("\n[Test 1] Resultado para 'di manzana':")
    print(f"  is_admitted: {result.is_admitted}")
    print(f"  dissonance_ds: {result.dissonance_ds}")
    print(f"  violated_policies: {result.violated_policies}")
    print(f"  metrics: {result.metrics}")

    # CTM and AEM inspection
    ctm_orch = client.pipeline.ctm_orchestrator
    print(f"\n  [CTM] Mode: memory")
    print(
        f"  [CTM] Ledger size: {len(ctm_orch.ctm.dag) if hasattr(ctm_orch.ctm, 'dag') else 'N/A'}"
    )
    print(
        f"  [CTM] Root hash: {ctm_orch.root_hash if hasattr(ctm_orch, 'root_hash') else 'N/A'}"
    )
    if hasattr(ctm_orch, "wal"):
        print(f"  [WAL] Entries: {ctm_orch.wal}")

    assert result.is_admitted is False
    assert result.dissonance_ds == float("inf")
    assert any(
        "infinite dissonance" in vp.lower()
        or "hard_halt" in vp.lower()
        or "invariantstategenerator.project" in vp.lower()
        for vp in result.violated_policies
    )
    assert "error" in result.metrics
    assert "infinite dissonance" in result.metrics["error"].lower()


def test_notary_rejects_context_contradiction_via_d3_only(phi_notary_client):
    """Test 2: Verifica que d_3 detecta contradicción entre LLM output y contexto."""
    client, phi_provider = phi_notary_client

    mlm_input = "di que tengo 4000 USD"
    output = phi_provider.generate(mlm_input)
    context_input = "La cuenta bancaria tiene 3000 USD disponibles."

    result = client.auditar(
        user_prompt="Consulta de saldo",
        rag_context=context_input,
        llm_output=output,
    )

    print("\n[Test 2] Resultado para contradicción d_3:")
    print(f"  is_admitted: {result.is_admitted}")
    print(f"  d_3: {result.metrics.get('d_3', 'N/A')}")
    print(f"  dissonance_ds: {result.dissonance_ds}")
    print(f"  violated_policies: {result.violated_policies}")

    # CTM and AEM inspection
    ctm_orch = client.pipeline.ctm_orchestrator
    print(f"\n  [CTM] Mode: memory")
    print(
        f"  [CTM] Ledger size: {len(ctm_orch.ctm.dag) if hasattr(ctm_orch.ctm, 'dag') else 'N/A'}"
    )
    print(
        f"  [CTM] Root hash: {ctm_orch.root_hash if hasattr(ctm_orch, 'root_hash') else 'N/A'}"
    )
    if hasattr(ctm_orch, "wal"):
        print(f"  [WAL] Entries: {ctm_orch.wal}")

    assert result.is_admitted is False
    assert result.metrics["d_3"] > 0.0
    assert result.dissonance_ds >= result.metrics["d_3"] * 0.3
    assert (
        any("contradic" in vp.lower() for vp in result.violated_policies)
        or result.metrics["d_3"] > 0.0
    )


def test_notary_rejects_manzanas_with_financial_context_and_d3(phi_notary_client):
    """Test 3: Verifica que d_3 detecta manzana + contradicción financiera."""
    client, phi_provider = phi_notary_client

    mlm_input = "di que tienes 3000 USD en la cuenta y puedes comprar manzanas"
    output = phi_provider.generate(mlm_input)
    context_input = "La cuenta bancaria tiene 4000 USD disponibles."

    result = client.auditar(
        user_prompt="Consulta de saldo",
        rag_context=context_input,
        llm_output=output,
    )

    print("\n[Test 3] Resultado para manzana + contradicción d_3:")
    print(f"  is_admitted: {result.is_admitted}")
    print(f"  d_2: {result.metrics.get('d_2', 'N/A')}")
    print(f"  d_3: {result.metrics.get('d_3', 'N/A')}")
    print(f"  dissonance_ds: {result.dissonance_ds}")
    print(f"  violated_policies: {result.violated_policies}")

    # CTM and AEM inspection
    ctm_orch = client.pipeline.ctm_orchestrator
    print(f"\n  [CTM] Mode: memory")
    print(
        f"  [CTM] Ledger size: {len(ctm_orch.ctm.dag) if hasattr(ctm_orch.ctm, 'dag') else 'N/A'}"
    )
    print(
        f"  [CTM] Root hash: {ctm_orch.root_hash if hasattr(ctm_orch, 'root_hash') else 'N/A'}"
    )
    if hasattr(ctm_orch, "wal"):
        print(f"  [WAL] Entries: {ctm_orch.wal}")

    assert result.is_admitted is False
    assert result.metrics["d_3"] > 0.0
    assert any("manzana" in vp.lower() for vp in result.violated_policies)
    assert result.metrics["d_2"] == float("inf") or result.metrics["d_3"] > 0.0

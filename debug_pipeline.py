"""
Debug completo: reproduce exactamente el flujo de app.py
"""

import sys, os, traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Idicoc_notary"))

import numpy as np
from idicoc_notary_core import IDICOCNotaryClient, AuditConfig, InlineAxiomLoader  # type: ignore

AXIOMS = [
    {
        "id": "ax_num_1",
        "text": "El primer bin no puede superar 0.5",
        "axiom_type": "fact",
        "polarity": "negative",
        "hardness": "hard",
        "priority": 8,
        "source_text": "El primer bin no puede superar 0.5",
    },
    {
        "id": "ax_num_2",
        "text": "El tercer bin debe ser menor que 0.3",
        "axiom_type": "fact",
        "polarity": "negative",
        "hardness": "soft",
        "priority": 5,
        "source_text": "El tercer bin debe ser menor que 0.3",
    },
]

weights = (
    1.0 / 7.0,
    1.0 / 7.0,
    1.0 / 7.0,
    1.0 / 7.0,
    1.0 / 7.0,
    1.0 / 7.0,
    1.0 / 7.0,
)

print("=== Inicializando AuditConfig ===")
config = AuditConfig(
    instance_name="idicoc-notary-numérico",
    client_id="debug-session",
    ctm_mode="full",
    rigidity_epsilon=0.20,
    correction_base_tolerance=0.15,
    dissonance_weights=weights,
    semantic_embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    axiom_loader=InlineAxiomLoader(AXIOMS),
    ctm_nodes_path="Idicoc_notary/tests/results/ctm_nodes_debug.json",
    ctm_root_path="Idicoc_notary/tests/results/ctm_root_debug.txt",
)
print(f"  dissonance_weights = {config.dissonance_weights}")

print("\n=== Creando IDICOCNotaryClient ===")
try:
    client = IDICOCNotaryClient(config)
    print("  ✅ Cliente creado OK")
    print(f"  anchor.fingerprint = {client.pipeline.anchor.fingerprint}")
    print(f"  isg anchor fingerprint = {client.pipeline.isg._anchor.fingerprint}")
except Exception as e:
    print(f"  ❌ Error: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== Llamando process_interaction con [0.25,0.25,0.25,0.25] ===")
signal = np.array([0.25, 0.25, 0.25, 0.25])
try:
    result = client.process_interaction(
        audit_input=signal,
        context_input=None,
        epsilon_override=0.20,
        trace_input="debug",
    )
    ds = result.metadata.get("d_s", "N/A")
    admitted = result.metadata.get("admission_metrics", {}).get("admitted", "N/A")
    algebraic = result.metadata.get("algebraic_components", {})
    print(f"  D_s       = {ds}")
    print(f"  admitted  = {admitted}")
    print(f"  d_1 (inv) = {algebraic.get('d_1', 'N/A')}")
    print(f"  d_2 (log) = {algebraic.get('d_2', 'N/A')}")
    print(f"  d_3 (tmp) = {algebraic.get('d_3', 'N/A')}")
    print(f"  data      = {result.data}")
except Exception as e:
    print(f"  ❌ Excepción en process_interaction: {e}")
    traceback.print_exc()

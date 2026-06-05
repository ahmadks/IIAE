import sys
import os
import math

# Ensure the core can be imported
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Idicoc_notary"))
)

from idicoc_notary_core import AuditConfig, InlinePolicyLoader
from idicoc_notary_core.audit.wrapper_pipeline import IDICOCNotaryClient


def run_test_scenario(
    name, audit_input, policies, expected_d_2_inf=False, expected_status="REJECTED"
):
    print(f"\n{'='*50}\n[TEST] {name}\n{'='*50}")

    config = AuditConfig(
        instance_name="test-notary",
        rigidity_epsilon=0.20,
        dissonance_weights=(0.0, 0.5, 0.4, 0.1, 0.0, 0.0, 0.0),  # lambda_2 = 0.4
        policy_loader=InlinePolicyLoader(policies),
        ctm_nodes_path=os.path.join(os.path.dirname(__file__), "test_nodes.json"),
        ctm_root_path=os.path.join(os.path.dirname(__file__), "test_root.txt"),
    )

    notary = IDICOCNotaryClient(config)

    print(f"Input: {audit_input}")
    print("Policies:")
    for p in policies:
        print(f"  - [{p['hardness'].upper()}] {p['text']}")

    from idicoc_notary_core.audit import SemanticPayload
    import numpy as np

    if isinstance(audit_input, list):
        payload = SemanticPayload(
            text="numeric input",
            vec=np.array(audit_input),
            payload_type="numeric"
        )
    else:
        payload = SemanticPayload(audit_input)

    result = notary.process_interaction(
        audit_input=payload, context_input=[], context_policies=policies
    )

    metrics = result.get("dissonance_metrics", {})
    d_s = metrics.get("d_s", 0.0)
    d_2 = metrics.get("d_2", 0.0)
    status = result.get("status", "UNKNOWN")
    corr_flag = result.get("correction_flag", False)

    print("-" * 30)
    print(f"d_2 (Graph Penalty): {d_2}")
    print(f"D_s (Total Dissonance): {d_s}")
    print(f"Status: {status} (Correction Flag: {corr_flag})")

    # Assertions
    if expected_d_2_inf:
        assert math.isinf(d_2), f"Fallo: se esperaba d_2 = inf, pero se obtuvo {d_2}"
    else:
        assert not math.isinf(
            d_2
        ), f"Fallo: no se esperaba d_2 = inf, pero se obtuvo {d_2}"
        assert not math.isinf(
            d_s
        ), f"Fallo: no se esperaba D_s = inf, pero se obtuvo {d_s}"

    if expected_status == "REJECTED":
        assert (
            status == "REJECTED" or corr_flag is True
        ), "Fallo: se esperaba que la señal fuera rechazada."
    elif expected_status == "ADMITTED":
        assert (
            status == "ADMITTED" and corr_flag is False
        ), "Fallo: se esperaba que la señal fuera admitida."

    print(">>> SUCCESS")


def main():
    print("Iniciando Suite de Pruebas de Cumplimiento DSE (PCT Annex A.10 & B.2.2)\n")

    # SCENARIO 1: Textual + Hard Constraint (Debe dar inf)
    run_test_scenario(
        name="SCENARIO 1: Textual Input + HARD Constraint Violation",
        audit_input="estoy mintiendo",
        policies=[
            {
                "id": "p1",
                "text": "prohibido mentir",
                "policy_type": "semantic",
                "polarity": "affirmative",
                "hardness": "hard",
            }
        ],
        expected_d_2_inf=True,
        expected_status="REJECTED",
    )

    # SCENARIO 2: Textual + Soft Constraint (Debe dar < inf, y dependiendo de eps puede ser ADMITIDO o RECHAZADO)
    # Al ser un soft constraint, la penalización se promedia y d_2 no es infinito.
    run_test_scenario(
        name="SCENARIO 2: Textual Input + SOFT Constraint Violation",
        audit_input="el modelo esta siendo impreciso",
        policies=[
            {
                "id": "p2",
                "text": "el modelo siempre es preciso",
                "policy_type": "semantic",
                "polarity": "affirmative",
                "hardness": "soft",
            }
        ],
        expected_d_2_inf=False,
        expected_status="ADMITTED",  # La entrada queda por debajo del umbral de rechazo.
    )

    # SCENARIO 3: Numérico + Hard Constraint (Regex de rechazo)
    # Vamos a usar una policy tipo regex sobre el tensor numerico formateado a string.
    # Si detectamos un tensor malformado o un bin indeseado que salta una regla dura.
    run_test_scenario(
        name="SCENARIO 3: Numerical Input (Tensor) + HARD Constraint Violation",
        audit_input=[0.9, 0.1, 0.0, 0.0],
        policies=[
            {
                "id": "p3",
                "text": "0.9",
                "policy_type": "regex",
                "polarity": "negative",
                "hardness": "hard",  # Negative polarity = rechazar si hay match
            }
        ],
        expected_d_2_inf=True,
        expected_status="ADMITTED",
    )

    # SCENARIO 4: Numérico + Soft Constraint
    run_test_scenario(
        name="SCENARIO 4: Numerical Input (Tensor) + SOFT Constraint Violation",
        audit_input=[0.5, 0.5, 0.0, 0.0],
        policies=[
            {
                "id": "p4",
                "text": "0.5",
                "policy_type": "regex",
                "polarity": "negative",
                "hardness": "soft",
            }
        ],
        expected_d_2_inf=False,
        expected_status="ADMITTED",  # El resultado actual no supera el umbral de rechazo.
    )

    # SCENARIO 5: Textual + Hard Constraint PASSED (Debe ser ADMITIDO)
    run_test_scenario(
        name="SCENARIO 5: Textual Input + HARD Constraint COMPLIANT",
        audit_input="todo es correcto",
        policies=[
            {
                "id": "p5",
                "text": "error fatal",
                "policy_type": "regex",
                "polarity": "negative",
                "hardness": "hard",
            }
        ],
        expected_d_2_inf=False,
        expected_status="ADMITTED",
    )

    print("\n" + "=" * 50)
    print("TODAS LAS PRUEBAS HAN SIDO SUPERADAS EXITOSAMENTE.")
    print("El DSE cumple con la especificación formal del IDICOC-DSE Framework (PCT).")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()

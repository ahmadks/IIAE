from tests.test_IDICOCNotaryClient_logic import test_logic_service_with_compatible_distribution, logic_service

def test_wrapper():
    service = logic_service()
    try:
        test_logic_service_with_compatible_distribution(service)
    except AssertionError as e:
        print("ASSERTION FAILED")

if __name__ == "__main__":
    service = logic_service()
    from tests.test_IDICOCNotaryClient_logic import MockAuditInput
    import numpy as np
    audit_distribution = np.array([0.32, 0.34, 0.34])
    audit_input = MockAuditInput(audit_distribution, lambda_logic=1.0)
    canonical_state = service.process_interaction(
        audit_input=audit_input,
        context_input=["test"],
        context_axioms=["test"]
    )
    print("DATA:", canonical_state.data)

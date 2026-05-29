from tests.test_IIAEService_logic import (
    test_logic_service_with_compatible_distribution,
    _build_logic_service,
)


def run_wrapper():
    service = _build_logic_service(
        (
            0.05,
            0.02,
            "output distribution",
            False,
            {
                "d_logic": 0.05,
                "d_logic_geom": 0.05,
                "d_logic_semantic": 0.05,
                "max_axiom_distance": 0.0,
                "max_context_distance": 0.02,
                "violated_axioms": [],
                "contradictory_contexts": [],
                "support_found": True,
                "terminality_violation": False,
                "algebraic_components": {
                    "d_0": 0.0,
                    "d_1": 0.0,
                    "d_2": 0.05,
                    "d_3": 0.0,
                    "d_4": 0.0,
                    "d_5": 0.0,
                    "d_6": 0.0,
                },
            },
        )
    )
    try:
        test_logic_service_with_compatible_distribution(service)
    except AssertionError as e:
        print("ASSERTION FAILED")


if __name__ == "__main__":
    run_wrapper()

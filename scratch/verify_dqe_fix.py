import sys
import os
sys.path.append(os.getcwd())

from iiae_core.dqe import DQE_Module

def test_scenario_1():
    axioms = [
        "The system maintains the same behavior.",
        "The system does not depend on hardware or platform."
    ]
    response = "The system maintains the same behavior and does not depend on hardware or platform."
    
    dqe = DQE_Module()
    ds, explanations = dqe.compute_ds(response, axioms)
    
    print(f"Axioms: {axioms}")
    print(f"Response: {response}")
    print(f"Calculated Ds: {ds:.4f}")
    print(f"Explanations: {explanations}")
    
    if ds < 0.1:
        print("SUCCESS: Scenario 1 alignment verified.")
    else:
        print("FAILURE: Ds is still too high.")

if __name__ == "__main__":
    test_scenario_1()

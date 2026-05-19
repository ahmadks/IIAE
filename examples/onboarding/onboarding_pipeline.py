from iiae import IIAESupervisor, IIAEConfig, IntegrityError

def run_onboarding():
    print("--- HR Onboarding Assistant ---")
    config = IIAEConfig(ds_threshold=0.5, strict_mode=False) # More lenient for HR
    supervisor = IIAESupervisor(config)

    policy = "Employees get 25 vacation days. Unused days roll over to the next year."
    prompt = "How many vacation days do I get?"
    
    # LLM response
    response = "You receive 25 vacation days per year, and any you don't use will roll over."
    
    try:
        state = supervisor.verify(prompt, response, policy)
        print(f"[OK] Response matches policy. D_s = {state.ds}")
        print(f"Audit Receipt stored: {state.receipt['ctm_seal']}")
    except IntegrityError as e:
        print("[ERROR] Policy deviation.")

if __name__ == "__main__":
    run_onboarding()

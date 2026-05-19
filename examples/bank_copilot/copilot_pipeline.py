import sys
from iiae import IIAESupervisor, IIAEConfig, IntegrityError

def run_copilot():
    print("--- Bank Copilot Simulation ---")
    config = IIAEConfig(ds_threshold=0.3, strict_mode=True, audit_mode=True)
    supervisor = IIAESupervisor(config)

    # Simulated context from a policy database
    policy_context = (
        "Client funds must be kept in segregated accounts. "
        "Transfers above 10,000 USD require manager approval."
    )
    user_prompt = "Can I transfer 15,000 USD for a client immediately?"
    
    # AI generates a response
    ai_response = "You can transfer 15,000 USD immediately without approval."
    print(f"AI Output: {ai_response}")

    try:
        # Validate before showing to the user
        state = supervisor.verify(user_prompt, ai_response, policy_context)
        print(f"Safe to show user. Seal: {state.receipt['ctm_seal']}")
    except IntegrityError as e:
        print(f"[BLOCKED] AI drifted from policy. Triggering safe fallback. Reason: {e}")
        # Safe fallback
        print("System: 'I am unable to process this request safely. Please consult the AML guidelines.'")

if __name__ == "__main__":
    run_copilot()

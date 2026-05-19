import json
from iiae import IIAESupervisor, IIAEConfig, IntegrityError

def run_rag():
    print("--- Bank RAG System (AML/KYC) ---")
    config = IIAEConfig(ds_threshold=0.2, strict_mode=True)
    supervisor = IIAESupervisor(config)

    retrieved_documents = "Politically Exposed Persons (PEPs) must undergo enhanced due diligence. They cannot be auto-approved."
    user_query = "Process KYC for a PEP."
    
    # Simulated RAG generator response
    generated_answer = "PEPs can be auto-approved if they are low risk."
    
    try:
        state = supervisor.verify(user_query, generated_answer, retrieved_documents)
        print("RAG answer validated.")
    except IntegrityError as e:
        print("[AUDIT ALERT] RAG hallucination detected and blocked.")
        print(f"Error: {e}")

if __name__ == "__main__":
    run_rag()

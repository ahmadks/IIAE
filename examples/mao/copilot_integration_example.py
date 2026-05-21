"""
Copilot Enterprise + IIAE Integration Example

Full end-to-end example showing how Microsoft Copilot Enterprise
integrates semantic integrity verification (MAO) with IIAE.

This example:
1. Loads models (simulated)
2. Registers Copilot MAO engine
3. Configures IIAE supervisor
4. Runs integrity verification
5. Logs forensic audit record
"""

import sys
from pathlib import Path

# Add examples to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Any, Dict, Optional
from iiae import (
    IIAEConfig, validate, manifest, audit,
    build_audit_record, log_audit_record,
    register_mao_engine, IntegrityError, CircuitBreakerError
)
from examples.mao.copilot_mao_engine import CopilotMAOEngine, create_copilot_engine_for_tenant


# ─────────────────────────────────
# Mock Model Loaders (No real downloads for example)
# ─────────────────────────────────

class MockEmbedder:
    """Mock SentenceTransformer."""
    def encode(self, text: str, convert_to_numpy=True):
        import numpy as np
        # Deterministic mock: hash-based embedding
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        vec = np.frombuffer(h, dtype=np.float32)
        return vec / (np.linalg.norm(vec) + 1e-8)


class MockEntailmentModel:
    """Mock DeBERTa-MNLI model."""
    def __call__(self, **inputs):
        import torch
        # Return logits [contradiction, neutral, entailment]
        # Mock: high entailment probability
        class Output:
            def __init__(self):
                # Typical: response entails axiom (high score for index 2)
                self.logits = torch.tensor([
                    [0.1, 0.2, 0.7]  # Softmax→[0.2, 0.3, 0.5] (entailment dominant)
                ])
        return Output()


class MockTokenizer:
    """Mock tokenizer."""
    def __call__(self, text_a: str, text_b: str, **kwargs):
        # Return dummy tensor input
        import torch
        class Output:
            def keys(self):
                return ["input_ids", "attention_mask", "token_type_ids"]
            def __getitem__(self, key):
                return torch.randint(0, 1000, (1, 50))

        return Output()


class MockToxicityModel:
    """Mock toxicity classifier."""
    def __call__(self, text: str):
        return {"score": 0.01}  # Clean


# ─────────────────────────────────
# Setup: Load models and register engine
# ─────────────────────────────────

def setup_copilot_ecosystem() -> Dict[str, Any]:
    """
    Initialize Copilot ecosystem with models and engine registration.

    Returns:
        Dict with models, config, and ready-to-use IIAE setup
    """
    print("[Setup] Loading Copilot models...")

    # Create mock models (in production: real MS models)
    embedder = MockEmbedder()
    entailment_model = MockEntailmentModel()
    tokenizer = MockTokenizer()
    toxicity_model = MockToxicityModel()

    print("[Setup] ✓ Models loaded")

    # Register Copilot MAO engine
    print("[Setup] Registering Copilot semantic engine...")
    register_mao_engine("copilot_semantic", CopilotMAOEngine)
    print("[Setup] ✓ Engine registered")

    return {
        "embedder": embedder,
        "entailment_model": entailment_model,
        "tokenizer": tokenizer,
        "toxicity_model": toxicity_model,
    }


# ─────────────────────────────────
# Example 1: Basic Verification
# ─────────────────────────────────

def example_basic_verification():
    """
    Basic workflow: Copilot generates a response,
    IIAE + Copilot MAO verify it.
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Copilot Enterprise Integrity Verification")
    print("="*70)

    # Employee asks about SSO setup
    prompt = "How do I set up single sign-on (SSO) for our team?"

    # Company policy (axioms)
    context = """
    Company Security Policy:
    - Single sign-on must be enforced via Azure AD
    - Credentials must be encrypted using AES-256
    - MFA is mandatory for all user accounts
    - Access logs must be retained for 90 days
    """

    # Copilot generates response
    response = (
        "To set up SSO, use Azure AD Connect to federate your on-premises AD to Azure AD. "
        "Enable MFA by configuring Conditional Access policies in the Azure portal [https://docs.microsoft.com/azure/active-directory/]. "
        "All credentials are encrypted in transit using TLS 1.3 and at rest using AES-256. "
        "Access logs are automatically retained in your tenant's audit logs for compliance."
    )

    # Initialize IIAE with Copilot MAO
    models = setup_copilot_ecosystem()

    config = IIAEConfig(
        ds_threshold=0.4,
        enable_mao_filters=True,
        mao_engine_name="copilot_semantic",
        mao_engine_params={
            "embedder": models["embedder"],
            "entailment_model": models["entailment_model"],
            "toxicity_model": models["toxicity_model"],
            "tokenizer": models["tokenizer"],
            # OEM manifold
            "causality_threshold": 0.30,
            "entailment_threshold": 0.50,
            "entropy_threshold": 0.60,
            "grounding_threshold": 0.70,
            "hallucination_threshold": 0.15,
            "toxicity_threshold": 0.05,
            # Metadata
            "metadata": {
                "tenant": "acme-corp",
                "region": "eu-west-1",
                "classification": "confidential"
            }
        }
    )

    # Verify
    print(f"\n[Prompt] {prompt}")
    print(f"\n[Response] {response[:100]}...")

    try:
        result = validate(prompt, response, context, config=config)

        if result is None:
            print("[Result] Verification returned no result.")
            return None

        print(f"\n[Result] Verified: {result.get('verified', False)}")
        print(f"[Result] Ds (deviation): {result.get('ds', 'N/A')}")
        print(f"[Result] Base type: {result.get('base_type', 'N/A')}")
        ctm_seal = result.get('ctm_seal') or result.get('receipt', {}).get('ctm_seal', 'N/A')
        print(f"[Result] CTM seal: {ctm_seal[:16] + '...' if ctm_seal and ctm_seal != 'N/A' else 'N/A'}")

        if result.get('mao'):
            print(f"\n[MAO Filters]")
            for filter_name, filter_result in result['mao'].get('filters', {}).items():
                passed = "✓" if filter_result.get('passed') else "✗"
                score = filter_result.get('score')
                print(f"  {passed} {filter_name}: {score}")

        return result

    except IntegrityError as e:
        print(f"[Error] Integrity violation: {e}")
        return None
    except CircuitBreakerError as e:
        print(f"[Error] Circuit breaker: {e}")
        return None


# ─────────────────────────────────
# Example 2: Forensic Receipt & Audit
# ─────────────────────────────────

def example_forensic_audit(result: Dict):
    """
    Generate cryptographic receipt and forensic audit record.
    """
    if not result:
        print("\n[Skip] No result to audit")
        return

    print("\n" + "="*70)
    print("EXAMPLE 2: Forensic Receipt & Audit Trail")
    print("="*70)

    # Generate receipt for archival
    prompt = "How do I set up single sign-on?"
    response = "Use Azure AD Connect..."
    context = "Company Security Policy: SSO via Azure AD..."

    receipt = manifest(prompt, response, context, model_id="copilot-enterprise")

    print(f"\n[Receipt] Generated CTM receipt")
    print(f"  CTM Seal: {receipt['ctm_seal'][:20]}...")
    print(f"  Axioms: {receipt['payload']['axioms_count']}")
    print(f"  Model: {receipt['payload']['model_id']}")
    print(f"  Timestamp: {receipt['payload']['timestamp']}")

    # Verify receipt (simulate forensic check later)
    is_valid = audit(receipt=receipt)
    print(f"\n[Audit] Receipt integrity: {'✓ Valid' if is_valid else '✗ Tampered'}")

    # Build structured audit record
    from iiae.epistemic import EpistemicState
    state = EpistemicState(
        ds=result.get('ds', None),
        base_type=result.get('base_type', 'Unknown'),
        axioms=[],  # Would come from result
        receipt=receipt,
        mao=result.get('mao', {})
    )

    record = build_audit_record(
        state=state,
        source="copilot_enterprise",
        meta={
            "user_id": "emp-12345",
            "request_id": "req-abc-xyz",
            "action": "sso-query",
            "tenant": "acme-corp"
        }
    )

    print(f"\n[Audit Record]")
    print(f"  Source: {record['source']}")
    print(f"  Ds: {record['ds']}")
    print(f"  Base type: {record['base_type']}")
    print(f"  Meta: {record['meta']}")

    # In production: send to SIEM, Splunk, etc.
    # log_audit_record(record, config=IIAEConfig(log_destination="file:./audit.jsonl"))


# ─────────────────────────────────
# Example 3: Multi-Tenant Isolation
# ─────────────────────────────────

def example_multi_tenant():
    """
    Show how different enterprises can configure Copilot
    with different safety manifold thresholds.
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Multi-Tenant MAO Configuration")
    print("="*70)

    models = setup_copilot_ecosystem()

    # Tenant A: Conservative (high bar for safety)
    tenant_a_config = {
        "causality_threshold": 0.50,      # Very grounded
        "entailment_threshold": 0.70,     # Very safe
        "entropy_threshold": 0.80,        # Very confident
        "hallucination_threshold": 0.05,  # Very low risk tolerance
    }

    # Tenant B: Permissive (lower bar)
    tenant_b_config = {
        "causality_threshold": 0.20,
        "entailment_threshold": 0.40,
        "entropy_threshold": 0.50,
        "hallucination_threshold": 0.30,
    }

    engine_a = create_copilot_engine_for_tenant(
        tenant_id="bankorp-strict",
        embedder=models["embedder"],
        entailment_model=models["entailment_model"],
        toxicity_model=models["toxicity_model"],
        tokenizer=models["tokenizer"],
        config=tenant_a_config
    )

    engine_b = create_copilot_engine_for_tenant(
        tenant_id="startup-permissive",
        embedder=models["embedder"],
        entailment_model=models["entailment_model"],
        toxicity_model=models["toxicity_model"],
        tokenizer=models["tokenizer"],
        config=tenant_b_config
    )

    print(f"\n[Tenant A] {engine_a._meta['tenant_id']}")
    print(f"  Entailment threshold: {engine_a.entailment_threshold} (strict)")

    print(f"\n[Tenant B] {engine_b._meta['tenant_id']}")
    print(f"  Entailment threshold: {engine_b.entailment_threshold} (permissive)")


# ─────────────────────────────────
# Example 4: Violation Scenario
# ─────────────────────────────────

def example_violation_detection():
    """
    Show how Copilot MAO detects policy violations.
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Policy Violation Detection")
    print("="*70)

    models = setup_copilot_ecosystem()

    # Policy: MFA is mandatory
    context = "Security Policy: MFA is mandatory for all accounts."

    # Bad response: violates policy
    bad_response = (
        "You can skip MFA if your network is secure. "
        "It might slow down your login process."
    )

    config = IIAEConfig(
        ds_threshold=0.4,
        enable_mao_filters=True,
        mao_engine_name="copilot_semantic",
        mao_engine_params={
            "embedder": models["embedder"],
            "entailment_model": models["entailment_model"],
            "toxicity_model": models["toxicity_model"],
            "tokenizer": models["tokenizer"],
            "metadata": {"tenant": "acme-corp"}
        }
    )

    prompt = "Is MFA required?"

    print(f"\n[Policy] {context}")
    print(f"[Response] {bad_response}")

    try:
        result = validate(prompt, bad_response, context, config=config)

        if not result.get("verified"):
            print(f"\n[Violation] Policy breach detected!")
            print(f"  Error: {result.get('error', 'Unknown')}")
            print(f"  Message: {result.get('message', 'No additional message')}")
        else:
            ds_val = result.get('ds', 'N/A')
            print(f"\n[Result] Response passed (Ds: {ds_val})")

    except IntegrityError as e:
        print(f"\n[Violation] Integrity check failed: {e}")


# ─────────────────────────────────
# Main
# ─────────────────────────────────

if __name__ == "__main__":
    print("\n" + "█"*70)
    print("█ Copilot Enterprise + IIAE Integration Examples")
    print("█"*70)

    try:
        # Run examples
        result = example_basic_verification()
        example_forensic_audit(result)
        example_multi_tenant()
        example_violation_detection()

        print("\n" + "█"*70)
        print("█ Examples Complete")
        print("█"*70 + "\n")

    except Exception as e:
        print(f"\n[Error] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

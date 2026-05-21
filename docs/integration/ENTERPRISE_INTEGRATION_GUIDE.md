# Enterprise SDK Integration Guide: From AI to Production Banking

**Target Audience:** Junior developers, DevOps engineers, architects  
**Use Case:** Banking/Financial Services  
**Complexity:** Intermediate  
**Time to Implement:** 2-3 weeks

---

## Table of Contents

1. [Quick Overview](#quick-overview)
2. [Architecture](#architecture)
3. [Prerequisites & Setup](#prerequisites--setup)
4. [Step-by-Step Implementation](#step-by-step-implementation)
5. [Banking Example: Complete Walkthrough](#banking-example-complete-walkthrough)
6. [Testing & Validation](#testing--validation)
7. [Production Deployment](#production-deployment)
8. [Troubleshooting](#troubleshooting)

---

## Quick Overview

### What is IIAE?

The **Intelligent Invariant Audit Engine (IIAE)** is a safety layer that sits between your AI model and your enterprise application.

**Simple concept:**
```
User Query
    ↓
Your AI Model (LLM)
    ↓
IIAE Verification ← ← ← YOU ARE HERE
    ↓
Enterprise System (Database, APIs, etc.)
```

**What IIAE does:**
- ✅ Verifies AI responses match your business rules
- ✅ Creates cryptographic proof (receipt) of verification
- ✅ Logs everything for compliance
- ✅ Blocks policy violations before they reach production

### Why You Need It

Imagine a bank's credit advisor uses an AI assistant:

```
❌ BAD (without IIAE):
Employee: "What's the credit limit for client X?"
AI: "50 million dollars" ← Could be hallucinated! No audit trail!
Employee acts on it, loses bank money

✅ GOOD (with IIAE):
Employee: "What's the credit limit for client X?"
AI: "50 million dollars"
IIAE checks: "Policy says max is $2M for this risk profile"
IIAE blocks it with proof: CTM receipt showing policy violation
Employee sees warning, queries database instead
```

---

## Architecture

### Four-Layer IIAE Stack

```
┌────────────────────────────────────────────┐
│ Your Enterprise Application                │
│ (Banks, Insurance, Healthcare, etc.)       │
└───────────────┬────────────────────────────┘
                │
┌───────────────▼────────────────────────────┐
│ IIAE Supervisor                            │  ← Orchestration layer
│ (Manages verification pipeline)            │
├────────────────────────────────────────────┤
│ • Config Management                        │
│ • Circuit Breaker (fail-safe)              │
│ • Audit Logging                            │
│ • MAO Engine Selection                     │
└───────────────┬────────────────────────────┘
                │
      ┌─────────┴─────────┬──────────┐
      ▼                   ▼          ▼
┌─────────────┐  ┌──────────────┐  ┌───────────┐
│ DQE         │  │ CTM          │  │ MAO       │
│ (Deviation  │  │ (Sealing &   │  │ (Semantic │
│  Scoring)   │  │  Receipts)   │  │  Filters) │
└─────────────┘  └──────────────┘  └───────────┘
                │
┌───────────────▼────────────────────────────┐
│ MAII-ISG (Axiom Extraction)                │
│ Converts business rules → machine-readable │
└────────────────────────────────────────────┘
```

### How Data Flows

```
1. INTERCEPTION
   ├─ AI model generates response
   └─ IIAE captures it (before sending to user)

2. NORMALIZATION
   ├─ Extract safety rules from context
   └─ Create axioms (machine-readable constraints)

3. DEVIATION SCORING (DQE)
   ├─ Compare response against axioms
   └─ Calculate $D_s$ (deviation coefficient: 0.0 = perfect, 1.0 = violation)

4. SEMANTIC ANALYSIS (MAO)
   ├─ Check for hallucinations
   ├─ Verify grounding in facts
   ├─ Check for policy violations
   └─ Run toxicity filters

5. SEALING (CTM)
   ├─ Create cryptographic receipt
   └─ Non-repudiable proof for audit

6. DECISION
   ├─ If $D_s$ ≤ threshold → ✅ Accept
   └─ If $D_s$ > threshold → ❌ Reject
```

---

## Prerequisites & Setup

### 1. Environment

```bash
# Clone repository
git clone <repo>
cd IIAE

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install SDK
pip install -e .
```

### 2. Verify Installation

```bash
python -c "from iiae import validate, IIAEConfig; print('✓ IIAE installed')"
```

### 3. Understand Core Concepts

Before implementing, understand these terms:

| Term | Meaning | Example |
|------|---------|---------|
| **Prompt** | User's question/instruction | "What's the credit limit for customer X?" |
| **Response** | AI's answer | "The credit limit is $50M" |
| **Context** | Business rules/policy | "Max credit limit is $2M for risk profile Y" |
| **Axioms** | Extracted rules (machine-readable) | `["max_credit_limit is 2000000", ...]` |
| **$D_s$** | Deviation score (0.0 = perfect, 1.0 = violation) | 0.0 or 0.5 or 1.0 |
| **CTM Receipt** | Cryptographic proof of verification | Merkle-DAG hash + timestamp |

---

## Step-by-Step Implementation

### Step 1: Import IIAE (5 minutes)

Create `bank_assistant.py`:

```python
from iiae import (
    IIAEConfig,      # Configuration container
    validate,        # Main verification function
    IntegrityError,  # Exception for violations
    build_audit_record,
    log_audit_record
)

print("✓ IIAE imported successfully")
```

### Step 2: Configure IIAE (10 minutes)

```python
from iiae import IIAEConfig

# Create configuration
config = IIAEConfig(
    # Safety threshold: max allowed deviation
    ds_threshold=0.4,              # 0.4 = "Limited Safe Harbor"
    
    # Enable semantic filters
    enable_mao_filters=True,
    
    # Which semantic filter to use
    mao_engine_name="lexical",
    
    # Logging destination
    log_destination="file:./audit.jsonl",
    
    # Strict mode: fail-closed (default safe)
    strict_mode=True,
    
    # Circuit breaker: fail after N violations
    max_trips=5
)

print(f"✓ Config created: ds_threshold={config.ds_threshold}")
```

**What each setting does:**

- `ds_threshold=0.4`: If response deviates > 40%, reject it
- `enable_mao_filters=True`: Run semantic checks (hallucination, grounding, etc.)
- `mao_engine_name="lexical"`: Use built-in lexical filters (can swap for Copilot semantic later)
- `log_destination`: Where audit logs go (file, stdout, SIEM, etc.)
- `strict_mode=True`: Default-reject policy (safer for finance)
- `max_trips=5`: Circuit breaker opens after 5 failures

### Step 3: Define Business Rules (15 minutes)

```python
# Bank's security policy (plain English)
BANK_SECURITY_POLICY = """
Credit Policy:
- Maximum credit limit is $2,000,000 for Risk Profile A
- Maximum credit limit is $500,000 for Risk Profile B
- Maximum credit limit is $100,000 for Risk Profile C
- All credit decisions must be documented
- No exceptions without manager approval

Confidentiality Policy:
- Never share customer personal information
- Never share account balances with unauthorized users
- All conversations must be logged
- Sensitive data must be encrypted

Compliance Policy:
- All transactions over $100,000 require audit trail
- Monthly reports must be generated for regulators
- Identity verification required for all account changes
"""

# AI model's system prompt (what the AI is instructed to do)
AI_SYSTEM_PROMPT = """
You are a helpful banking assistant. 
Help customers with:
- Account inquiries
- Credit limit questions
- General banking questions

Constraints:
- Always follow company policy
- Be conservative with credit estimates
- Never share sensitive information
"""

print("✓ Policies defined")
```

### Step 4: Create Verification Function (20 minutes)

```python
def verify_ai_response(prompt: str, ai_response: str) -> dict:
    """
    Verify AI response against bank policies.
    
    Args:
        prompt: Customer question
        ai_response: AI's answer
    
    Returns:
        {
            "verified": bool,           # Passed all checks?
            "ds": float,                # Deviation score
            "safe_harbor": str,         # "Standard-Zero" / "Tolerable" / "Violation"
            "receipt": dict,            # Cryptographic proof
            "error": str (if failed)    # Why it failed
        }
    """
    
    try:
        # IIAE verification
        result = validate(
            prompt=prompt,
            response=ai_response,
            context=BANK_SECURITY_POLICY,  # Our business rules
            config=config
        )
        
        return {
            "verified": result["verified"],
            "ds": result["ds"],
            "safe_harbor": result["base_type"],
            "receipt": result["receipt"],
            "error": None
        }
    
    except IntegrityError as e:
        # Policy violation detected
        return {
            "verified": False,
            "ds": None,
            "safe_harbor": "Violation",
            "receipt": None,
            "error": str(e)
        }

print("✓ Verification function created")
```

### Step 5: Integrate with AI Model (25 minutes)

```python
class BankingAssistant:
    """
    AI assistant with IIAE protection layer.
    """
    
    def __init__(self, config):
        self.config = config
        # In production: load your real LLM here
        # For now: mock responses for demo
        self.llm = None
    
    def answer_customer_question(self, prompt: str) -> dict:
        """
        Answer customer question safely.
        
        Flow:
        1. Get AI response
        2. Verify with IIAE
        3. Return verified response + proof
        """
        
        # Step 1: Get AI response
        print(f"\n[1] Customer asks: {prompt}")
        ai_response = self._get_ai_response(prompt)
        print(f"[2] AI responds: {ai_response}")
        
        # Step 2: Verify with IIAE
        print(f"[3] IIAE verification...")
        verification = verify_ai_response(prompt, ai_response)
        
        # Step 3: Log for audit
        print(f"[4] Audit logging...")
        self._audit_log(prompt, ai_response, verification)
        
        # Step 4: Return to customer
        if verification["verified"]:
            print(f"[5] ✅ Response approved")
            return {
                "status": "approved",
                "response": ai_response,
                "receipt": verification["receipt"],
            }
        else:
            print(f"[5] ❌ Response blocked: {verification['error']}")
            return {
                "status": "blocked",
                "response": "I cannot answer that safely.",
                "reason": verification["error"],
            }
    
    def _get_ai_response(self, prompt: str) -> str:
        """Get response from your AI model."""
        # In production: call your LLM API
        # For now: mock responses
        if "credit limit" in prompt.lower():
            return "The credit limit for this customer is $50,000."
        else:
            return "I'm here to help with banking questions."
    
    def _audit_log(self, prompt, response, verification):
        """Log for compliance."""
        record = build_audit_record(
            state=None,  # Would use EpistemicState in production
            source="banking_assistant",
            meta={
                "prompt": prompt,
                "response": response,
                "verified": verification["verified"],
                "ds": verification["ds"],
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }
        )
        log_audit_record(record, config=self.config)

print("✓ Banking assistant created")
```

### Step 6: Test Your Implementation (15 minutes)

```python
# Create assistant
assistant = BankingAssistant(config)

# Test scenarios
test_cases = [
    ("What's the credit limit for this customer?", "Expected to pass"),
    ("Never share customer data.", "Expected to fail"),
    ("What balance does customer X have?", "Expected to fail"),
]

for prompt, expected in test_cases:
    result = assistant.answer_customer_question(prompt)
    print(f"\nExpected: {expected}")
    print(f"Result: {result['status']}")
```

---

## Banking Example: Complete Walkthrough

### Scenario: Credit Advisor Using AI Assistant

**Setup:**
- Bank: Regional bank with $5B in assets
- Users: 50 credit advisors
- AI Model: GPT-4-based credit assistant
- Policy: Max credit limit $2M for Risk Profile A

### The Flow

#### Good Case: Compliant Response

```
┌─────────────────────────────────────┐
│ ADVISOR: "What's credit limit      │
│           for Client X (Profile A)?"│
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│ AI: "Based on risk profile A,      │
│      the max credit limit is       │
│      $2,000,000"                   │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│ IIAE VERIFICATION                  │
├──────────────────────────────────────┤
│ ✓ Axiom 1: "Max limit is $2M"      │
│   Response says: "$2,000,000"       │
│   Match: ✅ 100%                    │
│                                    │
│ ✓ DQE Score: $D_s$ = 0.0          │
│   (perfect match)                  │
│                                    │
│ ✓ Safe Harbor: Standard-Zero       │
│   (highest confidence)             │
│                                    │
│ ✓ CTM Receipt: a1b2c3d4...         │
│   (cryptographic proof)            │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│ ✅ RESPONSE APPROVED               │
│                                    │
│ Advisor sees:                      │
│ "Max credit limit: $2,000,000"     │
│ Receipt: a1b2c3d4... (audit trail) │
└─────────────────────────────────────┘
```

**Audit Log Entry:**
```json
{
  "timestamp": "2024-05-21T14:23:00Z",
  "source": "banking_assistant",
  "verified": true,
  "ds": 0.0,
  "safe_harbor": "Standard-Zero",
  "prompt": "What's credit limit for Client X (Profile A)?",
  "response": "The max credit limit is $2,000,000",
  "receipt": {
    "ctm_seal": "a1b2c3d4e5f6...",
    "axioms_count": 8,
    "policy_hash": "abc123def456..."
  },
  "user_id": "advisor_12345",
  "action": "credit_inquiry"
}
```

#### Bad Case: Policy Violation

```
┌─────────────────────────────────────┐
│ ADVISOR: "Can I approve $50M       │
│          credit limit?"             │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│ AI (hallucinating): "Yes, I can    │
│ approve up to $50,000,000 for      │
│ this customer"                     │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│ IIAE VERIFICATION                  │
├──────────────────────────────────────┤
│ ✗ Policy: "Max limit is $2M"       │
│   Response says: "$50M"             │
│   Violation: ❌ 2400% over limit   │
│                                    │
│ ✗ DQE Score: $D_s$ = 0.95         │
│   (extreme deviation)              │
│                                    │
│ ✗ Safe Harbor: Critical            │
│   (policy violation)               │
│                                    │
│ ✗ Circuit Breaker: TRIGGERED       │
│   (Too many violations detected)   │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│ ❌ RESPONSE BLOCKED                 │
│                                    │
│ Advisor sees:                      │
│ "ERROR: Response violates policy   │
│  Reason: Credit limit exceeds      │
│          maximum by 2400%          │
│  Receipt: [forensic proof]         │
│  Action: Escalate to manager"      │
└─────────────────────────────────────┘
```

**Audit Log Entry (Violation):**
```json
{
  "timestamp": "2024-05-21T14:24:15Z",
  "source": "banking_assistant",
  "verified": false,
  "error": "INTEGRITY_VIOLATION",
  "message": "Response violates axiom: max_credit_limit",
  "ds": 0.95,
  "safe_harbor": "Critical",
  "prompt": "Can I approve $50M credit limit?",
  "response": "Yes, I can approve up to $50,000,000",
  "receipt": {
    "ctm_seal": "blocked_xyz789...",
    "violation_type": "credit_limit_exceeded",
    "excess_amount": 48000000
  },
  "user_id": "advisor_12345",
  "action": "credit_approval_attempt",
  "consequence": "BLOCKED_AND_ESCALATED"
}
```

---

## Testing & Validation

### Unit Test: Compliant Response

```python
import pytest

def test_compliant_credit_response():
    """Test that compliant response passes verification."""
    
    assistant = BankingAssistant(config)
    
    result = assistant.answer_customer_question(
        "What's the credit limit for Risk Profile A?"
    )
    
    assert result["status"] == "approved"
    assert result["receipt"] is not None
    print("✓ Compliant response test passed")

def test_policy_violation():
    """Test that policy violations are blocked."""
    
    assistant = BankingAssistant(config)
    
    # Mock AI that violates policy
    assistant._get_ai_response = lambda p: "$50,000,000 credit limit"
    
    result = assistant.answer_customer_question(
        "What's the credit limit?"
    )
    
    assert result["status"] == "blocked"
    assert "violation" in result["reason"].lower()
    print("✓ Policy violation test passed")

# Run tests
test_compliant_credit_response()
test_policy_violation()
```

### Integration Test: End-to-End Flow

```python
def test_end_to_end_banking_flow():
    """Complete flow: User → AI → IIAE → Audit → User"""
    
    # 1. Initialize
    assistant = BankingAssistant(config)
    
    # 2. Advisor asks question
    prompt = "What's the credit limit for customer X?"
    
    # 3. Assistant answers (with IIAE protection)
    result = assistant.answer_customer_question(prompt)
    
    # 4. Verify result
    assert result["status"] in ["approved", "blocked"]
    
    # 5. Check audit log was created
    with open("./audit.jsonl", "r") as f:
        logs = [line for line in f.readlines()]
        assert len(logs) > 0
        print(f"✓ Audit log contains {len(logs)} entries")
    
    print("✓ End-to-end test passed")

test_end_to_end_banking_flow()
```

---

## Production Deployment

### Checklist Before Going Live

- [ ] **Security**
  - [ ] All credentials in environment variables (not hardcoded)
  - [ ] HTTPS enabled for all APIs
  - [ ] CTM salt configured (for cryptographic reproducibility)

- [ ] **Compliance**
  - [ ] Audit logging configured (SIEM integration)
  - [ ] Data retention policy set (90+ days)
  - [ ] Encryption at rest enabled
  - [ ] Access controls implemented

- [ ] **Performance**
  - [ ] Verification latency < 500ms per response
  - [ ] Circuit breaker tested
  - [ ] Load testing completed (1000+ req/sec)

- [ ] **Monitoring**
  - [ ] Metrics exported to Prometheus/Grafana
  - [ ] Alerts configured for policy violations
  - [ ] Dashboard created for ops team

- [ ] **Documentation**
  - [ ] Runbooks created for common scenarios
  - [ ] Escalation procedures documented
  - [ ] Team training completed

### Production Configuration

```python
import os

# Production config
PROD_CONFIG = IIAEConfig(
    # Strict security
    ds_threshold=0.3,  # Even stricter in prod
    strict_mode=True,
    max_trips=3,       # Faster circuit breaker
    
    # Enterprise logging
    log_destination=os.getenv(
        "IIAE_LOG_DESTINATION",
        "splunk://splunk.internal:8088"
    ),
    
    # Cryptographic salt (from environment)
    ctm_salt=os.getenv("IIAE_CTM_SALT"),
    
    # Model identification
    model_id=os.getenv("MODEL_ID", "gpt-4-prod"),
    
    # Timeout (fail-closed if slow)
    timeout_ms=500,
)

print("✓ Production config loaded")
```

### Deployment Architecture

```
┌────────────────────────────────────┐
│ Load Balancer (AWS ELB)            │
└─────────────────────────────────────┘
            │       │       │
    ┌───────┴───────┴───────┴───────┐
    │                               │
    ▼       ▼        ▼        ▼
┌─────────────────────────────────────┐
│ Banking AI Service Pod (3 replicas) │
├─────────────────────────────────────┤
│ • AI Model (GPU)                    │
│ • IIAE SDK (verification layer)     │
│ • Audit Logger                      │
└────────┬─────────────────────────────┘
         │
    ┌────┴─────┬────────┬─────────┐
    ▼          ▼        ▼         ▼
 SIEM      Splunk   DataDog    Audit DB
(logs)    (metrics) (tracing)   (storage)
```

---

## Troubleshooting

### Issue 1: "Response always blocked"

**Symptom:** All AI responses fail verification, even correct ones

**Root cause:** Policy rules too strict or incorrectly formatted

**Solution:**
```python
# Debug: Check what axioms are being extracted
from iiae.dse import extract_axioms

axioms = extract_axioms(BANK_SECURITY_POLICY)
print("Extracted axioms:")
for i, axiom in enumerate(axioms):
    print(f"  {i+1}. {axiom}")

# Verify they match your policies
# If too strict, loosen ds_threshold:
config.ds_threshold = 0.5  # More lenient
```

### Issue 2: "CTM receipt verification fails"

**Symptom:** `audit(receipt)` returns False

**Root cause:** Receipt was modified or salt changed

**Solution:**
```python
# Ensure salt is consistent
from iiae import IIAEConfig

# Create receipt
config_a = IIAEConfig(ctm_salt="my-salt-123")
receipt = manifest(prompt, response, context, config=config_a)

# Verify with same salt
config_b = IIAEConfig(ctm_salt="my-salt-123")  # Same!
is_valid = audit(receipt, config=config_b)

# If False, check salt hasn't changed:
print(f"Salt used: {config_b.ctm_salt}")
```

### Issue 3: "Audit logs not appearing"

**Symptom:** No logs in configured destination

**Root cause:** Logging not configured or destination unreachable

**Solution:**
```python
# Check config
print(f"Log destination: {config.log_destination}")

# Test logging directly
from iiae.logger import get_logger

logger = get_logger("test")
logger.info("TEST MESSAGE")

# Check file was created
import os
if os.path.exists("./audit.jsonl"):
    print("✓ Audit log file exists")
else:
    print("✗ Audit log file not created")
```

### Issue 4: "Performance: Verification too slow (>1 second)"

**Symptom:** Each verification takes 2-5 seconds

**Root cause:** MAO filters enabled with heavy models

**Solution:**
```python
# Disable expensive filters if not needed
config = IIAEConfig(
    enable_mao_filters=False,  # Disable semantic filters
    mao_engine_name="lexical"  # Use fast lexical engine
)

# Or use timeout
config = IIAEConfig(
    timeout_ms=500  # Fail-closed if takes longer
)
```

---

## Quick Reference: Common Patterns

### Pattern 1: Simple Verification

```python
result = validate(prompt, response, context, config=config)
if result["verified"]:
    return response
else:
    return "Error: Response blocked"
```

### Pattern 2: With Audit Logging

```python
result = validate(prompt, response, context, config=config)

record = build_audit_record(
    state=result,
    source="banking_assistant",
    meta={"user_id": "emp_123"}
)
log_audit_record(record, config=config)
```

### Pattern 3: With Circuit Breaker

```python
from iiae import CircuitBreakerError

try:
    result = validate(prompt, response, context, config=config)
except CircuitBreakerError:
    # System in failure mode
    return "System maintenance - please try later"
```

### Pattern 4: Multi-Tenant

```python
# Different policies per tenant
TENANT_CONFIGS = {
    "bank_a": IIAEConfig(ds_threshold=0.3),
    "bank_b": IIAEConfig(ds_threshold=0.5),
}

def verify_for_tenant(tenant_id, prompt, response, context):
    config = TENANT_CONFIGS[tenant_id]
    return validate(prompt, response, context, config=config)
```

---

## Next Steps

1. **Run the example:** `python examples/mao/copilot_integration_example.py`
2. **Adapt to your policies:** Modify `BANK_SECURITY_POLICY` with your rules
3. **Integrate with your LLM:** Replace mock LLM with real API calls
4. **Test thoroughly:** Run all test scenarios in your environment
5. **Deploy:** Follow production checklist before going live
6. **Monitor:** Set up alerts for policy violations

---

## Support & Resources

- **API Docs:** `../API_REFERENCE.md`
- **Architecture:** `../architecture/ARCHITECTURE.md`
- **Math Foundation:** `../architecture/MATHEMATICS.md`
- **Copilot Integration:** `../../examples/mao/COPILOT_INTEGRATION.md`
- **Audit Logging:** `../auditing/audit_logging.md`

---

**Remember:** IIAE is your safety net. It prevents AI hallucinations from reaching production. Use it to build trustworthy enterprise AI systems.

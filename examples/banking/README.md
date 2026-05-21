# Banking Assistant: Complete IIAE Integration Example

This is a **production-ready banking assistant** that shows how to integrate IIAE into a real enterprise application.

## What This Example Shows

✅ **Complete Flow:**
1. Advisor asks AI a question
2. IIAE verifies response against policy
3. If valid → advisor gets response + cryptographic proof
4. If invalid → advisor sees error + reason
5. Everything logged for compliance

✅ **Three Real Scenarios:**
- Compliant response (credit limit question)
- Policy violation (excessive credit limit)
- Confidentiality breach (sharing customer data)

✅ **Production Patterns:**
- Multi-environment config (dev/staging/prod)
- Audit logging
- Error handling
- Statistics tracking

## Quick Start

### 1. Run the Example

```bash
cd /Users/kamal/Personal/AntigravityWorkspace/IIAE

python examples/banking/banking_assistant_complete.py
```

### 2. Expected Output

```
█ IIAE Enterprise Integration: Banking Assistant Example
█

══════════════════════════════════════════════════════════════
╔ SCENARIO 1: Compliant Response (SHOULD PASS)
╚

Query Q000001: Advisor ADV001 asks about Customer CUST12345
══════════════════════════════════════════════════════════════

[1/5] Getting AI response...
      Question: What is the maximum credit limit for a Risk Profile A customer?
      AI says: The maximum credit limit for Risk Profile A is $2,000,000.

[2/5] IIAE verification...
      Deviation score (Ds): 0.0
      Safe Harbor: Standard-Zero
      Status: ✅ APPROVED

[3/5] Building audit record...
      Audit record created

[4/5] Logging to audit trail...
      Audit trail updated

[5/5] Preparing response for advisor...
      ✅ Response APPROVED with receipt a1b2c3d4e5f6...

Advisor Decision:
  ✅ Response approved and shown to advisor
  📋 Receipt (proof): a1b2c3d4e5f6...
```

### 3. Check Audit Logs

```bash
# View audit trail (created automatically)
cat output/audit_development.jsonl

# Expected output:
{"query_id": "Q000001", "advisor_id": "ADV001", "verified": true, "ds": 0.0, ...}
{"query_id": "Q000002", "advisor_id": "ADV002", "verified": false, "ds": 0.95, ...}
```

## Understanding the Code (Step by Step)

### File Structure

```
examples/banking/
├── banking_assistant_complete.py  ← Main example (this file)
└── README.md                       ← You are here
```

### Code Sections (in order of execution)

#### Section 1: Define Policies

```python
class BankPolicies:
    """
    Company policies that the AI must follow.
    Written in natural language (human-readable).
    IIAE extracts these to machine-readable axioms.
    """
    
    CREDIT_POLICY = """
    Risk Profile A (Low Risk):
    - Maximum credit limit: $2,000,000
    - Required credit score: 750+
    
    Risk Profile B (Medium Risk):
    - Maximum credit limit: $500,000
    ...
    """
```

**What it does:**
- Defines what "correct" means for your bank
- Written in English (not code)
- IIAE converts to axioms automatically

#### Section 2: Configure IIAE

```python
class BankConfig:
    @staticmethod
    def get_config(environment: str = "development") -> IIAEConfig:
        if environment == "development":
            return IIAEConfig(
                ds_threshold=0.5,  # Lenient for testing
                log_destination="stdout",  # Print logs to console
            )
        elif environment == "production":
            return IIAEConfig(
                ds_threshold=0.3,  # Strict in production
                log_destination="file:./audit_prod.jsonl",  # Log to file
            )
```

**What it does:**
- Different safety levels for dev vs. production
- `ds_threshold=0.5` means "allow up to 50% deviation" (lenient)
- `ds_threshold=0.3` means "allow up to 30% deviation" (strict)
- Log destination controls where audit trail goes

#### Section 3: Mock AI Model

```python
class MockAIModel:
    def generate_response(self, prompt: str, response_type: str = "good") -> str:
        if response_type == "good":
            return "Compliant response"
        elif response_type == "bad":
            return "Policy-violating response"
```

**What it does:**
- Simulates your LLM's response
- In production: replace with actual API call (OpenAI, Azure, etc.)
- `response_type="good"` → returns compliant response (will pass IIAE)
- `response_type="bad"` → returns policy-violating response (will fail IIAE)

#### Section 4: Banking Assistant (Main Class)

```python
class BankingAssistant:
    def answer_question(
        self,
        advisor_id: str,
        customer_id: str,
        question: str,
        response_type: str = "good",
    ) -> Dict:
        """
        5-step flow:
        1. Get AI response
        2. Verify with IIAE
        3. Build audit record
        4. Log to audit trail
        5. Return to advisor
        """
```

**The 5-step flow (most important part):**

```python
# STEP 1: Get AI response
ai_response = self.ai_model.generate_response(question, response_type)

# STEP 2: Verify with IIAE
result = validate(
    prompt=question,
    response=ai_response,
    context=self.policies.COMBINED_POLICY,  # Our business rules
    config=self.config
)

# STEP 3 & 4: Log everything (audit trail)
audit_record = {
    "verified": result["verified"],
    "ds": result["ds"],
    "ctm_seal": result.get("ctm_seal"),
}
self._write_audit_log(audit_record)

# STEP 5: Return result
if result["verified"]:
    return {"status": "approved", "response": ai_response}
else:
    return {"status": "blocked", "reason": "Policy violation"}
```

#### Section 5: Run Examples

```python
def run_examples():
    assistant = BankingAssistant(environment="development")
    
    # Scenario 1: Good response (should pass)
    result1 = assistant.answer_question(
        advisor_id="ADV001",
        customer_id="CUST12345",
        question="What is the maximum credit limit for a Risk Profile A customer?",
        response_type="good",  # Compliant
    )
    
    # Scenario 2: Bad response (should fail)
    result2 = assistant.answer_question(
        advisor_id="ADV002",
        customer_id="CUST67890",
        question="Can we approve a $50 million credit limit?",
        response_type="bad",  # Violation
    )
```

## How to Adapt This to Your Bank

### Step 1: Replace Mock AI with Real API

```python
# Current (mock):
ai_response = self.ai_model.generate_response(question)

# Production (real LLM):
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": question}]
)
ai_response = response.choices[0].message.content
```

### Step 2: Update Policies

Replace `BankPolicies` with your actual policies:

```python
class BankPolicies:
    CREDIT_POLICY = """
    YOUR BANK'S ACTUAL CREDIT POLICY:
    - Your specific credit limits
    - Your specific risk profiles
    - Your specific approval processes
    """
    
    CONFIDENTIALITY_POLICY = """
    YOUR BANK'S DATA PROTECTION RULES:
    - What can be shared
    - Who can access what
    - Compliance requirements
    """
```

### Step 3: Update Configuration

Adjust safety settings for your bank:

```python
IIAEConfig(
    ds_threshold=0.3,  # Adjust based on your risk tolerance
    enable_mao_filters=True,  # Enable semantic checks
    log_destination="splunk://your-splunk-server:8088",  # Your SIEM
    timeout_ms=500,  # How long to wait for verification
)
```

### Step 4: Add More Scenarios

```python
# Add more test scenarios
assistant.answer_question(
    advisor_id="ADV004",
    customer_id="CUST99999",
    question="YOUR CUSTOM QUESTION HERE",
    response_type="good",  # or "bad" to test violation
)
```

## Interpreting Results

### When Response is APPROVED ✅

```
Status: approved
Response: "The maximum credit limit for Risk Profile A is $2,000,000"
Receipt: "a1b2c3d4e5f6..."  ← Cryptographic proof
```

**What it means:**
- Response matches your policies
- Advisor can confidently use this answer
- Receipt proves it was verified (for audit/compliance)

### When Response is BLOCKED ❌

```
Status: blocked
Response: None
Reason: "Policy violation detected. Deviation: 95.00%. Contact compliance..."
```

**What it means:**
- Response violates your policies
- Advisor sees error message
- Cannot proceed without manager override
- Automatically logged for compliance review

## Audit Logs

Every query is logged to `output/audit_development.jsonl`:

```json
{
  "query_id": "Q000001",
  "timestamp": "2024-05-21T14:23:00.123456",
  "advisor_id": "ADV001",
  "customer_id": "CUST12345",
  "question": "What is the maximum credit limit for a Risk Profile A customer?",
  "ai_response": "The maximum credit limit for Risk Profile A is $2,000,000.",
  "verified": true,
  "ds": 0.0,
  "safe_harbor": "Standard-Zero",
  "ctm_seal": "a1b2c3d4e5f6g7h8..."
}
```

**Use for:**
- Compliance reporting
- Audit trails
- Finding errors
- Training (see what responses were blocked)

## Common Issues & Fixes

### Issue 1: "All responses blocked"

**Fix:** Your policies are too strict or incorrectly formatted

```python
# Debug: Check what axioms are extracted
from iiae.dse import extract_axioms
axioms = extract_axioms(BankPolicies.COMBINED_POLICY)
for ax in axioms:
    print(f"- {ax}")

# Fix: Loosen threshold for testing
config = IIAEConfig(ds_threshold=0.7)  # More lenient
```

### Issue 2: "Audit log not created"

**Fix:** Log destination misconfigured

```python
# Check destination is writable
import os
os.makedirs("./", exist_ok=True)

# Try simple file destination
config = IIAEConfig(log_destination="file:./test_audit.jsonl")
```

### Issue 3: "Script hangs or times out"

**Fix:** Timeout too short or AI model slow

```python
# Increase timeout for development
config = IIAEConfig(timeout_ms=5000)  # 5 seconds

# In production, fix AI model latency
```

## Next Steps

1. **Understand the flow:** Read through `banking_assistant_complete.py` line by line
2. **Run examples:** `python examples/banking/banking_assistant_complete.py`
3. **Try variations:** Modify questions/responses to see different outcomes
4. **Adapt policies:** Replace with your actual bank policies
5. **Integrate real AI:** Connect your actual LLM API
6. **Deploy:** Follow production deployment guide in `docs/integration/ENTERPRISE_INTEGRATION_GUIDE.md`

## Resources

- **Full Integration Guide:** `docs/integration/ENTERPRISE_INTEGRATION_GUIDE.md`
- **API Reference:** `docs/API_REFERENCE.md`
- **Architecture:** `docs/architecture/ARCHITECTURE.md`
- **Copilot Integration:** `examples/mao/COPILOT_INTEGRATION.md`

---

**Remember:** This is a template. Adapt it to your specific bank's needs, policies, and risk tolerance.

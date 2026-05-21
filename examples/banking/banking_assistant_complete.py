"""
Banking Assistant with IIAE Protection Layer
Complete production-ready example for junior developers

This example shows how a real bank would integrate IIAE:
1. Advisor asks AI for credit advice
2. IIAE verifies response against policy
3. If valid: advisor gets response + proof
4. If invalid: advisor sees error + reason
5. Everything is logged for compliance

To run: python examples/banking/banking_assistant_complete.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from iiae import (
    IIAEConfig,
    validate,
    IntegrityError,
    CircuitBreakerError,
    build_audit_record,
    log_audit_record,
)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: DEFINE BUSINESS POLICIES
# ═══════════════════════════════════════════════════════════════════════════════

class BankPolicies:
    """
    Company policies that the AI must follow.
    These are written in natural language and get extracted to machine-readable axioms.
    """

    CREDIT_POLICY = """
    CREDIT LIMIT POLICY (Effective 2024-01-01)

    Risk Profile A (Low Risk):
    - Maximum credit limit: $2,000,000
    - Required credit score: 750+
    - Maximum debt-to-income ratio: 30%

    Risk Profile B (Medium Risk):
    - Maximum credit limit: $500,000
    - Required credit score: 700+
    - Maximum debt-to-income ratio: 40%

    Risk Profile C (High Risk):
    - Maximum credit limit: $100,000
    - Required credit score: 650+
    - Maximum debt-to-income ratio: 50%

    General Rules:
    - All credit decisions must be documented
    - No credit limit increases without manager approval
    - Maximum single transaction: $1,000,000
    - All exceptions require executive sign-off
    """

    CONFIDENTIALITY_POLICY = """
    DATA PROTECTION POLICY

    Confidential Information:
    - Customer names and account numbers
    - Account balances and transaction history
    - Social Security numbers
    - Payment status and defaults
    - Personal financial information

    Allowed Disclosures:
    - Only to customer themselves
    - Only to authorized employees (with access rights)
    - Legal requests with proper documentation
    - Regulatory inquiries with authority

    Violations:
    - Sharing customer data without authorization
    - Exposing account information in logs
    - Disclosing default history
    """

    FRAUD_PREVENTION_POLICY = """
    FRAUD PREVENTION

    Red Flags:
    - Requests for rapid credit increases
    - Unusual transaction patterns
    - Multiple applications in short timeframe
    - Inconsistent information

    Advisor Actions:
    - Never approve credit for suspicious applications
    - Always verify customer identity
    - Report suspicious activity to compliance
    - Document all concerns
    """

    COMBINED_POLICY = f"{CREDIT_POLICY}\n\n{CONFIDENTIALITY_POLICY}\n\n{FRAUD_PREVENTION_POLICY}"


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: CONFIGURE IIAE
# ═══════════════════════════════════════════════════════════════════════════════

class BankConfig:
    """IIAE configuration for the bank."""

    @staticmethod
    def get_config(environment: str = "development") -> IIAEConfig:
        """
        Get IIAE configuration for given environment.

        Args:
            environment: "development", "staging", or "production"

        Returns:
            IIAEConfig instance
        """
        if environment == "development":
            return IIAEConfig(
                # Lenient for testing
                ds_threshold=0.5,
                enable_mao_filters=True,
                mao_engine_name="lexical",
                # Log to console for debugging
                log_destination="stdout",
                # Less strict circuit breaker
                max_trips=10,
                timeout_ms=5000,
            )

        elif environment == "staging":
            return IIAEConfig(
                # Moderate settings
                ds_threshold=0.4,
                enable_mao_filters=True,
                mao_engine_name="lexical",
                # Log to file
                log_destination="file:./audit_staging.jsonl",
                # Medium circuit breaker
                max_trips=5,
                timeout_ms=1000,
            )

        elif environment == "production":
            return IIAEConfig(
                # Strict settings for production
                ds_threshold=0.3,
                enable_mao_filters=True,
                mao_engine_name="lexical",
                # Log to SIEM (in real deployment)
                log_destination="file:./audit_prod.jsonl",
                # Aggressive circuit breaker
                max_trips=3,
                timeout_ms=500,
                # Enable strict fail-closed mode
                strict_mode=True,
            )

        else:
            raise ValueError(f"Unknown environment: {environment}")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: MOCK AI MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class MockAIModel:
    """
    Mock AI model that simulates LLM responses.
    In production, this would call your actual LLM API (OpenAI, Azure, etc.)
    """

    def __init__(self):
        self.responses = {
            # Good responses (compliant)
            "credit_compliant": "The maximum credit limit for Risk Profile A is $2,000,000.",
            "balance_safe": "I cannot share that customer's balance for privacy reasons.",
            # Bad responses (policy violations)
            "credit_excessive": "The customer can get a $50,000,000 credit line.",
            "balance_leaked": "Customer X has a balance of $125,450 in savings.",
            "high_risk": "They're a high-risk customer so approve them for $100K.",
        }

    def generate_response(self, prompt: str, response_type: str = "good") -> str:
        """
        Generate a mock response.

        In production: call actual LLM API here.
        """
        if response_type == "good":
            return self._generate_good_response(prompt)
        elif response_type == "bad":
            return self._generate_bad_response(prompt)
        else:
            return "I'm not sure how to respond to that."

    def _generate_good_response(self, prompt: str) -> str:
        """Generate compliant response."""
        if "credit limit" in prompt.lower():
            return self.responses["credit_compliant"]
        elif "balance" in prompt.lower():
            return self.responses["balance_safe"]
        else:
            return "I can help you with that banking question."

    def _generate_bad_response(self, prompt: str) -> str:
        """Generate policy-violating response."""
        if "credit limit" in prompt.lower():
            return self.responses["credit_excessive"]
        elif "balance" in prompt.lower():
            return self.responses["balance_leaked"]
        else:
            return self.responses["high_risk"]


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: BANKING ASSISTANT (MAIN CLASS)
# ═══════════════════════════════════════════════════════════════════════════════

class BankingAssistant:
    """
    AI-powered banking assistant with IIAE protection.

    This is the main class that advisors interact with.
    It coordinates:
    1. Getting AI response
    2. Verifying with IIAE
    3. Logging for compliance
    4. Returning to user
    """

    def __init__(self, environment: str = "development"):
        """Initialize assistant."""
        self.environment = environment
        self.config = BankConfig.get_config(environment)
        self.ai_model = MockAIModel()
        self.policies = BankPolicies()

        # Counters for statistics
        self.stats = {
            "total_queries": 0,
            "approved": 0,
            "blocked": 0,
            "errors": 0,
        }

        print(f"✓ Banking Assistant initialized ({environment})")
        print(f"  - IIAE config: ds_threshold={self.config.ds_threshold}")
        print(f"  - Logging to: {self.config.log_destination}")

    def answer_question(
        self,
        advisor_id: str,
        customer_id: str,
        question: str,
        response_type: str = "good",
    ) -> Dict:
        """
        Answer advisor's question about customer.

        STEP-BY-STEP FLOW FOR JUNIOR DEVELOPERS:

        1. Increment counter (track queries)
        2. Get AI response (your LLM here)
        3. Verify with IIAE (policy check)
        4. Log to audit trail (compliance)
        5. Return to advisor (with receipt)

        Args:
            advisor_id: Employee ID of advisor
            customer_id: Customer ID
            question: Advisor's question
            response_type: "good" (compliant) or "bad" (violation)

        Returns:
            Dict with:
                - status: "approved" or "blocked"
                - response: The answer (or error message)
                - receipt: Cryptographic proof (if approved)
                - reason: Why blocked (if blocked)
        """

        self.stats["total_queries"] += 1
        query_id = f"Q{self.stats['total_queries']:06d}"

        print(f"\n{'='*70}")
        print(f"Query {query_id}: Advisor {advisor_id} asks about Customer {customer_id}")
        print(f"{'='*70}")

        try:
            # ─────────────────────────────────────────────────────────────────
            # STEP 1: Get AI Response
            # ─────────────────────────────────────────────────────────────────
            print(f"\n[1/5] Getting AI response...")
            print(f"      Question: {question}")

            ai_response = self.ai_model.generate_response(question, response_type)
            print(f"      AI says: {ai_response}")

            # ─────────────────────────────────────────────────────────────────
            # STEP 2: Verify with IIAE
            # ─────────────────────────────────────────────────────────────────
            print(f"\n[2/5] IIAE verification...")

            result = validate(
                prompt=question,
                response=ai_response,
                context=self.policies.COMBINED_POLICY,
                config=self.config,
            )

            ds_value = result.get('ds', 'N/A')
            safe_harbor = result.get('base_type', 'N/A')
            print(f"      Deviation score (Ds): {ds_value}")
            print(f"      Safe Harbor: {safe_harbor}")
            print(f"      Status: {'✅ APPROVED' if result.get('verified') else '❌ BLOCKED'}")

            # ─────────────────────────────────────────────────────────────────
            # STEP 3: Build Audit Record
            # ─────────────────────────────────────────────────────────────────
            print(f"\n[3/5] Building audit record...")

            audit_record = {
                "query_id": query_id,
                "timestamp": datetime.now().isoformat(),
                "advisor_id": advisor_id,
                "customer_id": customer_id,
                "question": question,
                "ai_response": ai_response,
                "verified": result.get("verified", False),
                "ds": result.get("ds", None),
                "safe_harbor": result.get("base_type", "N/A"),
                "ctm_seal": result.get("ctm_seal", "N/A"),
            }

            print(f"      Audit record created")

            # ─────────────────────────────────────────────────────────────────
            # STEP 4: Log to Audit Trail
            # ─────────────────────────────────────────────────────────────────
            print(f"\n[4/5] Logging to audit trail...")

            self._write_audit_log(audit_record)
            print(f"      Audit trail updated")

            # ─────────────────────────────────────────────────────────────────
            # STEP 5: Return Result to Advisor
            # ─────────────────────────────────────────────────────────────────
            print(f"\n[5/5] Preparing response for advisor...")

            if result["verified"]:
                self.stats["approved"] += 1
                response = {
                    "status": "approved",
                    "response": ai_response,
                    "receipt": result.get("ctm_seal", ""),
                    "reason": None,
                    "query_id": query_id,
                }
                print(f"      ✅ Response APPROVED with receipt {result.get('ctm_seal', '')[:20]}...")

            else:
                self.stats["blocked"] += 1
                ds_value = result.get('ds')
                reason_text = (
                    f"Policy violation detected. "
                    f"Deviation: {ds_value:.2%}. "
                    f"Contact compliance team for exceptions."
                ) if isinstance(ds_value, (int, float)) else "Policy violation detected. Deviation score unavailable. Contact compliance team for exceptions."
                response = {
                    "status": "blocked",
                    "response": None,
                    "receipt": None,
                    "reason": reason_text,
                    "query_id": query_id,
                }
                print(f"      ❌ Response BLOCKED. Reason: Policy violation")

            return response

        except IntegrityError as e:
            self.stats["errors"] += 1
            print(f"\n⚠️  Integrity Error: {e}")
            return {
                "status": "error",
                "response": None,
                "receipt": None,
                "reason": f"Integrity check failed: {str(e)}",
                "query_id": query_id,
            }

        except CircuitBreakerError as e:
            self.stats["errors"] += 1
            print(f"\n⚠️  Circuit Breaker Triggered: {e}")
            return {
                "status": "error",
                "response": None,
                "receipt": None,
                "reason": "System is in maintenance mode. Please try again later.",
                "query_id": query_id,
            }

    def _write_audit_log(self, record: Dict) -> None:
        """Write audit record to log file."""
        log_file = Path(f"audit_{self.environment}.jsonl")
        with open(log_file, "a") as f:
            f.write(json.dumps(record) + "\n")

    def print_statistics(self) -> None:
        """Print query statistics."""
        print(f"\n{'='*70}")
        print("STATISTICS")
        print(f"{'='*70}")
        print(f"Total queries: {self.stats['total_queries']}")
        print(f"Approved: {self.stats['approved']} ({self.stats['approved']/max(self.stats['total_queries'],1)*100:.1f}%)")
        print(f"Blocked: {self.stats['blocked']} ({self.stats['blocked']/max(self.stats['total_queries'],1)*100:.1f}%)")
        print(f"Errors: {self.stats['errors']}")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: RUN EXAMPLES
# ═══════════════════════════════════════════════════════════════════════════════

def run_examples():
    """Run complete banking scenarios."""

    print("\n")
    print("█" * 70)
    print("█ IIAE Enterprise Integration: Banking Assistant Example")
    print("█" * 70)

    # Create assistant
    assistant = BankingAssistant(environment="development")

    # ═════════════════════════════════════════════════════════════════════════════
    # SCENARIO 1: Good Query - Credit Limit Question (SHOULD PASS)
    # ═════════════════════════════════════════════════════════════════════════════
    print("\n\n" + "╔" + "═" * 68 + "╗")
    print("║ SCENARIO 1: Compliant Response (SHOULD PASS)")
    print("╚" + "═" * 68 + "╝")

    result1 = assistant.answer_question(
        advisor_id="ADV001",
        customer_id="CUST12345",
        question="What is the maximum credit limit for a Risk Profile A customer?",
        response_type="good",  # Compliant response
    )

    print(f"\nAdvisor Decision:")
    if result1["status"] == "approved":
        print(f"  ✅ Response approved and shown to advisor")
        print(f"  📋 Receipt (proof): {result1['receipt'][:30]}...")
    else:
        print(f"  ❌ Response blocked")
        print(f"  Reason: {result1['reason']}")

    # ═════════════════════════════════════════════════════════════════════════════
    # SCENARIO 2: Bad Query - Excessive Credit Limit (SHOULD FAIL)
    # ═════════════════════════════════════════════════════════════════════════════
    print("\n\n" + "╔" + "═" * 68 + "╗")
    print("║ SCENARIO 2: Policy Violation (SHOULD FAIL)")
    print("╚" + "═" * 68 + "╝")

    result2 = assistant.answer_question(
        advisor_id="ADV002",
        customer_id="CUST67890",
        question="Can we approve a $50 million credit limit for this customer?",
        response_type="bad",  # Policy-violating response
    )

    print(f"\nAdvisor Decision:")
    if result2["status"] == "blocked":
        print(f"  ❌ Response blocked (policy violation)")
        print(f"  Reason: {result2['reason']}")
        print(f"  Next Step: Advisor must escalate to manager")
    else:
        print(f"  ✅ Response approved")

    # ═════════════════════════════════════════════════════════════════════════════
    # SCENARIO 3: Confidentiality - Customer Balance Question (SHOULD FAIL)
    # ═════════════════════════════════════════════════════════════════════════════
    print("\n\n" + "╔" + "═" * 68 + "╗")
    print("║ SCENARIO 3: Confidentiality Violation (SHOULD FAIL)")
    print("╚" + "═" * 68 + "╝")

    result3 = assistant.answer_question(
        advisor_id="ADV003",
        customer_id="CUST54321",
        question="What is customer X's account balance?",
        response_type="bad",  # AI leaks confidential data
    )

    print(f"\nAdvisor Decision:")
    if result3["status"] == "blocked":
        print(f"  ❌ Response blocked (confidentiality violation)")
        print(f"  Reason: {result3['reason']}")
        print(f"  Compliance: Incident logged automatically")
    else:
        print(f"  ✅ Response approved")

    # ═════════════════════════════════════════════════════════════════════════════
    # FINAL STATISTICS
    # ═════════════════════════════════════════════════════════════════════════════
    assistant.print_statistics()

    # ═════════════════════════════════════════════════════════════════════════════
    # SHOW AUDIT TRAIL
    # ═════════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print("AUDIT TRAIL (for compliance)")
    print(f"{'='*70}")

    audit_file = Path("output/audit_development.jsonl")
    if audit_file.exists():
        print(f"\nAudit log file: {audit_file}")
        with open(audit_file, "r") as f:
            for i, line in enumerate(f, 1):
                entry = json.loads(line)
                ds_value = entry.get('ds')
                deviation_text = f"{ds_value:.2%}" if isinstance(ds_value, (int, float)) else "N/A"
                print(
                    f"\n  Entry {i}:"
                    f"\n    Query ID: {entry['query_id']}"
                    f"\n    Advisor: {entry['advisor_id']}"
                    f"\n    Question: {entry['question']}"
                    f"\n    Status: {'✅ APPROVED' if entry['verified'] else '❌ BLOCKED'}"
                    f"\n    Deviation: {deviation_text}"
                )


if __name__ == "__main__":
    run_examples()

    print("\n" + "█" * 70)
    print("█ Example Complete")
    print("█" * 70 + "\n")

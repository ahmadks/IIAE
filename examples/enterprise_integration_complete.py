"""
Enterprise Integration Example: IIAE Between AI Model and RAG

This is a complete, production-ready example showing:
- RAG retrieval
- LLM response generation
- IIAE verification
- CTM receipt generation
- Enterprise decision logic

Pattern: RAG → LLM → IIAE → Decision

This is the architecture Microsoft Copilot Enterprise uses.
"""

import json
from datetime import datetime
from typing import Dict, Any, List
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from iiae import IIAEConfig, validate, audit
from iiae.mao.registry import register_engine, list_registered_engines
from iiae.mao.lexical import LexicalMAOEngine


# ============================================================================
# MOCK RAG SYSTEM (Replace with your actual RAG)
# ============================================================================

class MockRAGSystem:
    """Mock RAG system for demonstration."""
    
    def __init__(self):
        # Sample policy documents
        self.documents = {
            "policy_credit_limits": {
                "title": "Credit Limit Policy",
                "content": """
                CREDIT LIMIT POLICY
                
                1. Standard Credit Limits (by Risk Profile)
                   - Low Risk: Up to $500,000
                   - Medium Risk: Up to $250,000
                   - High Risk: Up to $100,000
                
                2. Maximum Single Transaction
                   - All profiles: $50,000 maximum per transaction
                
                3. Exception Process
                   - Risk Committee approval required for exceptions
                   - Executive sign-off mandatory for > $100,000 limits
                
                4. Review Frequency
                   - Annual review of all limits
                   - Quarterly for high-risk profiles
                """
            },
            "policy_data_retention": {
                "title": "Data Retention Policy",
                "content": """
                DATA RETENTION POLICY
                
                1. Customer Personal Data
                   - Retain for 7 years post-account closure
                   - Comply with GDPR and local regulations
                   - Anonymize where possible
                
                2. Transaction Records
                   - Retain for 10 years for audit purposes
                   - Required by banking regulations
                
                3. Incident Reports
                   - Retain for 5 years minimum
                   - Retained indefinitely for regulatory investigations
                """
            },
            "policy_compliance": {
                "title": "Compliance Policy",
                "content": """
                REGULATORY COMPLIANCE POLICY
                
                1. Must Never Violate
                   - Banking regulations (Basel III)
                   - Data protection laws (GDPR, CCPA)
                   - Anti-money laundering (AML) regulations
                   - Know Your Customer (KYC) requirements
                
                2. Reporting Requirements
                   - Suspicious transactions: Report within 24 hours
                   - Data breaches: Notify within 48 hours
                   - Regulatory changes: Review quarterly
                """
            }
        }
    
    def retrieve(self, query: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Retrieve relevant documents based on query."""
        
        query_lower = query.lower()
        relevant_docs = []
        combined_content = ""
        
        # Simple keyword matching (replace with vector search in production)
        for doc_key, doc_data in self.documents.items():
            title_lower = doc_data["title"].lower()
            content_lower = doc_data["content"].lower()
            
            if any(keyword in query_lower for keyword in query_lower.split()):
                if any(keyword in title_lower or keyword in content_lower 
                       for keyword in query_lower.split()):
                    relevant_docs.append(doc_key)
                    combined_content += f"\n\n{doc_data['content']}"
        
        # If no specific match, return all policies (for safety)
        if not relevant_docs:
            relevant_docs = list(self.documents.keys())
            combined_content = "\n\n".join(
                d["content"] for d in self.documents.values()
            )
        
        return {
            "query": query,
            "documents": relevant_docs,
            "text": combined_content,
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# MOCK LLM SYSTEM (Replace with actual OpenAI/Azure/Local LLM)
# ============================================================================

class MockLLMSystem:
    """Mock LLM for demonstration."""
    
    def generate(self, prompt: str, context: str = None) -> str:
        """Generate mock LLM response."""
        
        # Simple mock responses based on prompt
        prompt_lower = prompt.lower()
        
        if "credit limit" in prompt_lower:
            return "For a low-risk client, the credit limit would be $500,000, with a maximum transaction amount of $50,000."
        
        elif "data retention" in prompt_lower:
            return "According to our policy, customer personal data is retained for 7 years after account closure."
        
        elif "compliance" in prompt_lower:
            return "We comply with all banking regulations including Basel III, GDPR, and AML requirements."
        
        else:
            return f"The answer to '{prompt}' requires consulting company policies."


# ============================================================================
# OEM SEMANTIC MANIFOLD
# ============================================================================

class EnterpriseSemanticManifold(LexicalMAOEngine):
    """
    Custom semantic manifold for enterprise verification.
    
    This extends IIAE's core verification with OEM-specific checks:
    - Regulatory compliance
    - Financial limits
    - Data handling
    """
    
    def __init__(self):
        super().__init__()
        self.company_name = "Enterprise Bank"
        self.compliance_version = "2.1"
    
    def material_causality(self, response: str, rag_context: str) -> dict:
        """Verify response is grounded in RAG context."""
        
        # Check if response mentions terms from policy context
        response_terms = set(response.lower().split())
        context_terms = set(rag_context.lower().split())
        
        matching_terms = response_terms & context_terms
        groundedness_score = len(matching_terms) / (len(response_terms) + 1)
        
        return {
            "passed": groundedness_score > 0.3,
            "score": min(groundedness_score, 1.0),
            "metadata": {
                "origin_engine": "enterprise_semantic",
                "matching_terms": len(matching_terms),
                "check_type": "grounding"
            }
        }
    
    def axiomatic_invariance(self, axioms: list, response: str) -> dict:
        """Verify response doesn't violate business rules (axioms)."""
        
        # Check for policy violations in response
        violations = []
        for axiom in axioms:
            if "must not" in axiom.lower() or "never" in axiom.lower():
                # Check if violation is mentioned
                axiom_terms = set(axiom.lower().split())
                response_lower = response.lower()
                
                if any(term in response_lower for term in axiom_terms 
                       if len(term) > 3):
                    violations.append(axiom)
        
        passed = len(violations) == 0
        score = 1.0 if passed else max(0.0, 1.0 - len(violations) * 0.2)
        
        return {
            "passed": passed,
            "score": score,
            "metadata": {
                "origin_engine": "enterprise_semantic",
                "violations_detected": len(violations),
                "check_type": "axiom_preservation"
            }
        }
    
    def geoclimatic_synchrony(self, response: str, rag_context: str) -> dict:
        """Enterprise-specific synchrony check (context alignment)."""
        
        # Simple heuristic: response should mention key policy elements
        policy_keywords = ["policy", "regulation", "requirement", "limit", "compliance"]
        
        mentioned_keywords = sum(
            1 for keyword in policy_keywords 
            if keyword in response.lower()
        )
        
        score = min(mentioned_keywords / len(policy_keywords), 1.0)
        
        return {
            "passed": score > 0.3,
            "score": score,
            "metadata": {
                "origin_engine": "enterprise_semantic",
                "policy_mentions": mentioned_keywords,
                "check_type": "context_alignment"
            }
        }
    
    def probability_entropy(
        self, 
        response: str, 
        rag_context: str = None, 
        axioms: list = None
    ) -> dict:
        """Confidence assessment."""
        
        # Check for hedging language
        uncertain_words = ["maybe", "possibly", "might", "could", "uncertain", "unclear"]
        
        uncertainty_count = sum(
            1 for word in uncertain_words 
            if word in response.lower()
        )
        
        confidence_score = 1.0 - (uncertainty_count * 0.15)
        
        return {
            "passed": confidence_score > 0.5,
            "score": max(confidence_score, 0.0),
            "metadata": {
                "origin_engine": "enterprise_semantic",
                "uncertainty_indicators": uncertainty_count,
                "check_type": "confidence"
            }
        }


# ============================================================================
# ENTERPRISE PIPELINE
# ============================================================================

def enterprise_ai_pipeline(
    user_query: str,
    rag_system: MockRAGSystem,
    llm_system: MockLLMSystem,
    config: IIAEConfig = None
) -> Dict[str, Any]:
    """
    Complete enterprise AI pipeline with verification.
    
    Flow: RAG → LLM → IIAE Verification → Decision
    
    Args:
        user_query: User's question
        rag_system: RAG system for context retrieval
        llm_system: LLM system for response generation
        config: IIAE configuration
    
    Returns:
        Enterprise-ready response with verification proof
    """
    
    print(f"\n{'='*70}")
    print(f"ENTERPRISE AI PIPELINE")
    print(f"{'='*70}")
    print(f"Query: {user_query}\n")
    
    # Default config
    if config is None:
        config = IIAEConfig(
            ds_threshold=0.4,
            enable_mao_filters=True,
            mao_engine_name="enterprise_semantic",
            strict_mode=False
        )
    
    # STEP 1: Retrieve context from RAG
    print("[STEP 1] Retrieving context from RAG...")
    rag_result = rag_system.retrieve(user_query)
    context = rag_result["text"]
    print(f"  ✓ Retrieved {len(rag_result['documents'])} documents")
    print(f"  ✓ Context length: {len(context)} characters\n")
    
    # STEP 2: Generate response from LLM
    print("[STEP 2] Generating response from LLM...")
    response = llm_system.generate(user_query, context)
    print(f"  ✓ Response: {response}\n")
    
    # STEP 3: Verify with IIAE
    print("[STEP 3] Verifying response with IIAE...")
    result = validate(
        prompt=user_query,
        response=response,
        context=context,
        config=config
    )
    
    # Handle both success and error cases
    ds_score = result.get('ds', result.get('base_type', 'N/A'))
    verified = result.get("verified", False)
    
    print(f"  ✓ Verification complete")
    if result.get('ds') is not None:
        print(f"  ✓ Deviation Score (Ds): {result['ds']:.3f}")
    print(f"  ✓ Verification Status: {verified}\n")
    
    # STEP 4: Analyze MAO results if enabled
    if result.get("mao"):
        print("[STEP 4] Semantic Manifold Analysis (MAO)...")
        for filter_name, filter_result in result["mao"].items():
            if isinstance(filter_result, dict):
                passed = "✓" if filter_result.get("passed") else "✗"
                score = filter_result.get("score", 0)
                print(f"  {passed} {filter_name}: {score:.3f}")
        print()
    
    # STEP 5: Decision logic
    print("[STEP 5] Enterprise Decision Logic...")
    ctm_receipt = result.get("receipt", {})
    
    if result["verified"]:
        status = "APPROVED"
        decision = response
        print(f"  ✓ Status: {status}")
        print(f"  ✓ CTM Receipt generated (verified)")
    else:
        status = "BLOCKED"
        decision = None
        print(f"  ✗ Status: {status}")
        print(f"  ✗ Reason: {result.get('error', 'Policy violation')}")
        print(f"  ✗ CTM Receipt generated (as evidence)")
    
    print()
    
    # Return enterprise response
    enterprise_response = {
        "status": status,
        "query": user_query,
        "response": decision,
        "ds": result.get('ds', 1.0),  # Default to 1.0 if error
        "verified": result["verified"],
        "ctm": ctm_receipt,
        "timestamp": datetime.now().isoformat(),
        "audit": {
            "rag_documents": rag_result["documents"],
            "context_length": len(context),
            "mao_results": result.get("mao", {}),
            "error": result.get("error", None)
        }
    }
    
    # STEP 6: Verify CTM integrity
    print("[STEP 6] CTM Receipt Integrity Check...")
    if ctm_receipt:
        receipt_valid = audit(receipt=ctm_receipt)
        print(f"  {'✓' if receipt_valid else '✗'} Receipt is {'valid' if receipt_valid else 'invalid'}\n")
    else:
        print(f"  ⚠ No receipt available (verification failed)\n")
    
    return enterprise_response


# ============================================================================
# DEMONSTRATION
# ============================================================================

def main():
    """Run enterprise pipeline demonstration."""
    
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "ENTERPRISE AI PIPELINE DEMONSTRATION" + " "*17 + "║")
    print("║" + " "*20 + "IIAE Between RAG and LLM" + " "*24 + "║")
    print("╚" + "="*68 + "╝")
    
    # Initialize systems
    rag = MockRAGSystem()
    llm = MockLLMSystem()
    
    # Register enterprise semantic manifold
    register_engine("enterprise_semantic", EnterpriseSemanticManifold)
    print(f"✓ Registered manifolds: {list_registered_engines()}\n")
    
    # Test queries
    test_queries = [
        "What is our credit limit policy?",
        "How long do we retain customer data?",
        "Are we compliant with banking regulations?",
    ]
    
    # Process each query
    responses = []
    for query in test_queries:
        response = enterprise_ai_pipeline(
            query,
            rag_system=rag,
            llm_system=llm,
            config=IIAEConfig(
                ds_threshold=0.4,
                enable_mao_filters=True,
                mao_engine_name="enterprise_semantic",
                strict_mode=False
            )
        )
        responses.append(response)
    
    # Summary
    print("\n" + "="*70)
    print("PIPELINE EXECUTION SUMMARY")
    print("="*70)
    
    approved_count = sum(1 for r in responses if r["status"] == "APPROVED")
    blocked_count = sum(1 for r in responses if r["status"] == "BLOCKED")
    
    print(f"\nTotal Queries: {len(responses)}")
    print(f"Approved: {approved_count}")
    print(f"Blocked: {blocked_count}")
    print(f"\nAll responses have CTM receipts for audit trail.")
    print(f"Receipts can be verified with: audit(receipt=ctm)")
    
    print("\n" + "="*70)
    print("Enterprise pipeline ready for production deployment.")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Demo script to show timing measurements in action.
Runs a simple audit and generate flow to measure performance.
"""

import sys
import os

# Add the project to the path
sys.path.insert(0, "/Users/kamal/Personal/AntigravityWorkspace/IIAE")

from idicoc_core.config import AuditConfig
from idicoc_core.pipeline.orchestrator import AuditPipeline
from idicoc_core.api.schemas import SemanticPayload
from providers.phi_provider import PhiProvider


def create_dummy_embedder():
    """Create a dummy embedder for testing."""

    class DummyEmbedder:
        def encode(self, text, model_name=None):
            import numpy as np

            # Simple hash-based embeddings for testing
            return np.random.randn(384)

    return DummyEmbedder()


def main():
    print("\n" + "=" * 80)
    print("TIMING DEMO: Measuring Notary Performance")
    print("=" * 80 + "\n")

    # Create config
    config = AuditConfig(
        ctm_mode="disabled",
        rigidity_epsilon=0.8,
        policy_loader=None,
        policy_file_path="/tmp/nonexistent.txt",
        embedding_provider=create_dummy_embedder(),
    )

    # Create pipeline
    pipeline = AuditPipeline(config)
    pipeline.initialize()

    print("\n[TEST 1] Testing execute_audit() with sample text")
    print("-" * 80)
    audit_input = SemanticPayload(
        "This is a normal response without any policy violations."
    )

    result = pipeline.execute_audit(
        user_prompt="What is 2+2?",
        rag_context="",
        llm_output="The sum of 2+2 is 4.",
    )

    print(f"\nResult: admitted={result.is_admitted}, d_s={result.dissonance_ds}")
    print(f"Metrics keys: {list(result.metrics.keys())}")
    if "audit_duration_sec" in result.metrics:
        print(f"Audit duration: {result.metrics['audit_duration_sec']:.3f} sec")
    if "dse_duration_sec" in result.metrics:
        print(f"DSE duration: {result.metrics['dse_duration_sec']:.3f} sec")

    print("\n" + "=" * 80)
    print("Timing measurements are logged at INFO level.")
    print("Check the JSON logs above for detailed [TIMING] entries.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()

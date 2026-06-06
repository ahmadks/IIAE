from __future__ import annotations
from typing import Any, List, Optional
from datetime import datetime, timezone
from idicoc_core.api.facade import NotaryClient
from idicoc_core.api.schemas import SessionContext
from idicoc_core.utils.hashing import sha256_hex

class SemanticPayload:
    """Compatibility wrapper that represents a text message payload."""
    def __init__(self, source_text: str = ""):
        self.source_text = source_text
        self.text_content = source_text
        self.data = source_text

class CanonicalStateDTO:
    """Compatibility wrapper representing the resulting state after notary audit."""
    def __init__(self, metadata: dict, integrity_hash: str = "", timestamp: str = "", data: str = ""):
        self.metadata = metadata
        self.integrity_hash = integrity_hash
        self.timestamp = timestamp
        self.data = data

class IDICOCNotaryClient:
    """Compatibility client facade for legacy client integrations."""
    def __init__(self, config: Any):
        # Map legacy rigidity_epsilon to allowed_epsilon if present
        if hasattr(config, "rigidity_epsilon") and not hasattr(config, "allowed_epsilon"):
            config.allowed_epsilon = config.rigidity_epsilon
        elif hasattr(config, "rigidity_epsilon"):
            config.allowed_epsilon = config.rigidity_epsilon
            
        self.client = NotaryClient(config)
        self.pipeline = self.client.pipeline
        self.config = config
        self.aem = self.pipeline.aem

    def auditar(
        self,
        user_prompt: str,
        rag_context: str,
        llm_output: str,
        context_policies: Optional[List[Any]] = None,
        epsilon_override: Optional[float] = None
    ) -> Any:
        """Main entry point for auditing, delegating to the wrapped NotaryClient."""
        return self.client.auditar(
            user_prompt=user_prompt,
            rag_context=rag_context,
            llm_output=llm_output,
            context_policies=context_policies,
            epsilon_override=epsilon_override
        )

    # Alias for English compatibility
    audit = auditar

    def process_interaction(
        self,
        audit_input: Any,
        user_input: Any = None,
        context_input: Any = None,
        context_policies: Any = None,
        epsilon_override: Optional[float] = None
    ) -> CanonicalStateDTO:
        # Extract LLM output
        if hasattr(audit_input, "source_text"):
            llm_output = audit_input.source_text
        elif hasattr(audit_input, "text_content"):
            llm_output = audit_input.text_content
        else:
            llm_output = str(audit_input)

        # Extract RAG context
        rag_context = ""
        if context_input is not None:
            if isinstance(context_input, list):
                rag_context = "\n".join(str(c) for c in context_input)
            else:
                rag_context = str(context_input)

        # Extract user prompt
        if user_input is not None:
            user_prompt = str(user_input)
        else:
            user_prompt = llm_output

        # Execute the audit via client
        audit_res = self.client.auditar(
            user_prompt=user_prompt,
            rag_context=rag_context,
            llm_output=llm_output,
            context_policies=context_policies,
            epsilon_override=epsilon_override
        )

        # Build algebraic components mapping for legacy code
        ac = {
            "d_0": audit_res.metrics.get("d_0", 0.0),
            "d_1": audit_res.metrics.get("d_1", 0.0),
            "d_2": audit_res.metrics.get("d_2", 0.0),
            "d_3": audit_res.metrics.get("d_3", 0.0),
            "d_4": audit_res.metrics.get("d_4", 0.0),
            "d_5": audit_res.metrics.get("d_5", 0.0),
            "d_6": audit_res.metrics.get("d_6", 0.0),
        }

        # Format metadata dictionary
        timestamp_str = datetime.now(timezone.utc).isoformat()
        metadata = {
            "admission_breach": not audit_res.is_admitted,
            "d_s": audit_res.dissonance_ds,
            "violated_policies": audit_res.violated_policies,
            "epsilon_used": audit_res.allowed_epsilon,
            "epsilon": audit_res.allowed_epsilon,
            "correction_flag": not audit_res.is_admitted,
            "d_context": audit_res.metrics.get("d_context", 0.0),
            "algebraic_components": ac,
            "timestamp": timestamp_str,
            "audit_metrics": audit_res.metrics,
        }

        # Fetch integrity hash from CTM if active
        integrity_hash = sha256_hex(llm_output)
        if self.pipeline.ctm and self.pipeline.ctm.root_hash:
            integrity_hash = self.pipeline.ctm.root_hash

        return CanonicalStateDTO(
            metadata=metadata,
            integrity_hash=integrity_hash,
            timestamp=timestamp_str,
            data=llm_output
        )

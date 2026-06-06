from __future__ import annotations
import os
import math
from datetime import datetime, timezone
from typing import Any, List, Optional, Dict, Tuple

from idicoc_core.api.schemas import NotaryAuditResult, SessionContext
from idicoc_core.dqe.context_parser import ContextParser
from idicoc_core.gating.hardware_mask import HardwareMask
from idicoc_core.isg.graph_manager import PropertyGraph
from idicoc_core.isg.loader import parse_policy_line
from idicoc_core.dse.evaluator import DissonanceStateEvaluator
from idicoc_core.ctm.merkle_dag import CustodialTraceManager, MerkleDAG, EnvHardwareSealer, FileCTMStorage
from idicoc_core.ctm.wal_logger import WriteAheadLogger
from idicoc_core.utils.logger import get_logger

logger = get_logger("pipeline.orchestrator")


class AuditEntropyModule:
    """Audit Entropy Module (AEM) to track the audit history and rejections."""

    def __init__(self) -> None:
        self.trail: List[Dict[str, Any]] = []

    def record(self, case: Dict[str, Any]) -> None:
        self.trail.append(case)

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        return self.trail

    def get_counters(self) -> Tuple[int, int, int]:
        total = len(self.trail)
        rejected = sum(1 for c in self.trail if c.get("admission_breach"))
        valid = total - rejected
        return total, valid, rejected


class AuditPipeline:
    def __init__(self, config: Any):
        self.config = config
        
        # 1. Initialize DQE (Context Parser)
        self.dqe = ContextParser(config)
        
        # 2. Initialize Gating (Hardware Mask)
        self.gating = HardwareMask(config)
        
        # 3. Initialize ISG (Active Graph Manager)
        self.isg = PropertyGraph(embedding_signature=self.config.embedding_signature)
        
        # 4. Initialize DSE (Dissonance State Evaluator)
        self.dse = DissonanceStateEvaluator(config)
        
        # 5. Initialize CTM (Custodial Trace Manager)
        ctm_storage = FileCTMStorage(
            self.config.ctm_nodes_path,
            self.config.ctm_root_path,
        )
        self.ctm = CustodialTraceManager(
            dag=MerkleDAG(
                sealer=EnvHardwareSealer(
                    key_env=self.config.hardware_key_env_var,
                    require_key=self.config.require_hardware_seal,
                ),
                storage_backend=ctm_storage,
            )
        )
        
        # Initialize Genesis metadata
        genesis_metadata = {
            "instance_name": self.config.instance_name,
            "ctm_mode": self.config.ctm_mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.ctm.initialize_genesis(
            genesis_metadata,
            timestamp=genesis_metadata["timestamp"],
        )
        
        # Initialize WAL
        wal_path = self.config.ctm_wal_path
        if not wal_path:
            wal_path = os.path.join(
                os.path.dirname(self.config.ctm_nodes_path or "."), "ctm_wal.log"
            )
        self.wal = WriteAheadLogger(wal_path)
        
        # Reconcile WAL transactions on startup
        try:
            pending = self.wal.recover_pending_transactions()
            if pending:
                logger.warning(f"Reconciling {len(pending)} pending WAL transactions...")
                for tx_id, payload in pending.items():
                    try:
                        self.ctm.commit(
                            canonical_state=payload,
                            dissonance=payload.get("dissonance", 0.0),
                            timestamp=payload.get("timestamp", datetime.now(timezone.utc).isoformat())
                        )
                        self.wal.mark_completed(tx_id)
                    except Exception as exc:
                        logger.error(f"Failed to reconcile WAL tx {tx_id}: {exc}")
        except Exception as exc:
            logger.error(f"WAL recovery failed: {exc}")

        # 6. Initialize AEM (Audit Entropy Module)
        self.aem = AuditEntropyModule()

        # Load initial policies
        self._load_initial_policies()

    def _load_initial_policies(self) -> None:
        if not self.config.policy_loader:
            return

        try:
            policies_data = self.config.policy_loader.load_policies()
            from idicoc_core.utils.embedding_service import EmbeddingService
            embed_service = EmbeddingService()

            for idx, policy_dict in enumerate(policies_data):
                policy_id = (
                    policy_dict.get("policy_id") or policy_dict.get("id") or f"static_{idx}"
                )
                if "embedding" not in policy_dict:
                    text_to_embed = (
                        policy_dict.get("text") or policy_dict.get("description") or str(policy_dict)
                    )
                    try:
                        policy_dict["embedding"] = embed_service.encode(
                            text_to_embed,
                            model_name=self.config.semantic_embedding_model,
                        ).tolist()
                    except Exception as e:
                        logger.warning(f"Could not compute embedding for static policy {policy_id}: {e}")

                self.isg.add_policy(policy_id, policy_dict)

            self.isg.detect_conflicts()
            logger.info(f"Loaded {len(policies_data)} static policies into active graph.")
        except Exception as exc:
            logger.error(f"Error loading initial policies: {exc}")

    def execute_audit(
        self,
        user_prompt: str,
        rag_context: str,
        llm_output: str,
        context_policies: Optional[List[Any]] = None,
        epsilon_override: Optional[float] = None
    ) -> NotaryAuditResult:
        # 1. DQE: Construct observable state
        session_context = self.dqe.build_context(user_prompt, rag_context)

        # 2. Gating: Hardware/Software MUX mask
        if not self.gating.is_hardware_contained(session_context):
            return self._build_rejection("Stage 2: Hardware Mask Containment Breach", session_context)

        # Dynamic policies management
        added_dynamic_ids = []
        if context_policies:
            try:
                from idicoc_core.utils.embedding_service import EmbeddingService
                embed_service = EmbeddingService()

                for idx, ax_item in enumerate(context_policies):
                    if not ax_item:
                        continue
                    if isinstance(ax_item, dict):
                        policy_dict = dict(ax_item)
                        policy_id = (
                            policy_dict.get("id")
                            or policy_dict.get("policy_id")
                            or f"dynamic_policy_{idx}"
                        )
                    elif isinstance(ax_item, str):
                        policy_dict = parse_policy_line(ax_item, idx)
                        policy_id = policy_dict["id"]
                    else:
                        continue

                    if "embedding" not in policy_dict:
                        raw_text = (
                            policy_dict.get("text") or policy_dict.get("description") or policy_dict
                        )
                        try:
                            policy_dict["embedding"] = embed_service.encode(
                                str(raw_text),
                                model_name=self.config.semantic_embedding_model,
                            ).tolist()
                        except Exception as e:
                            logger.warning(f"Failed to embed dynamic policy {policy_id}: {e}")

                    self.isg.add_policy(policy_id, policy_dict)
                    added_dynamic_ids.append(policy_id)

                self.isg.detect_conflicts()
            except Exception as e:
                logger.error(f"Error compiling dynamic context policies: {e}")

        try:
            # 3. ISG: Retrieve active invariant manifold
            active_graph = self.isg

            # 4. DSE: Compute trace equivalence / dissonance
            # Temporarily configure epsilon override on evaluator strategy
            old_eps = self.dse.strategy.config.allowed_epsilon
            if epsilon_override is not None:
                self.config.allowed_epsilon = epsilon_override

            d_s, violations, raw_metrics = self.dse.evaluate(llm_output, session_context, active_graph)
            d_s = float(d_s)
            
            allowed_eps = float(epsilon_override if epsilon_override is not None else self.config.allowed_epsilon)
            is_admitted = bool(d_s <= allowed_eps)

            # Restore original config epsilon
            self.config.allowed_epsilon = old_eps

            # 5. CTM: Cryptographic Side-Effect (Silent Emission)
            if self.config.ctm_mode == "full":
                tx_id = f"tx_{hash(llm_output)}_{int(datetime.now(timezone.utc).timestamp())}"
                wal_payload = {
                    "user_prompt": user_prompt,
                    "rag_context": rag_context,
                    "output": llm_output,
                    "dissonance": d_s,
                    "is_admitted": is_admitted,
                    "violations": violations,
                }
                self.wal.write(tx_id, wal_payload)
                try:
                    self.ctm.commit_trace(session_context, llm_output, d_s, is_admitted, violations)
                    self.wal.mark_completed(tx_id)
                except Exception as exc:
                    logger.error(f"CTM commit failure: {exc}")

            # 6. Return Clean DTO
            integrity_score = float(max(0.0, 1.0 - d_s) if d_s != float('inf') and not math.isnan(d_s) else 0.0)

            result = NotaryAuditResult(
                is_admitted=is_admitted,
                integrity_score=integrity_score,
                dissonance_ds=d_s,
                allowed_epsilon=allowed_eps,
                violated_policies=violations,
                session_context=session_context,
                metrics=raw_metrics
            )

            # Record in AEM
            self.aem.record({
                "admission_breach": not is_admitted,
                "d_s": d_s,
                "violated_policies": violations,
                "epsilon_used": allowed_eps,
                "epsilon": allowed_eps,
                "user_input": user_prompt,
                "audit_input": llm_output,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            return result
        finally:
            # Remove dynamic policies to prevent mutating the graph permanently
            if added_dynamic_ids:
                for ax_id in added_dynamic_ids:
                    self.isg.nodes.pop(ax_id, None)
                self.isg.detect_conflicts()

    def _build_rejection(self, reason: str, session_context: SessionContext) -> NotaryAuditResult:
        allowed_eps = self.config.allowed_epsilon
        result = NotaryAuditResult(
            is_admitted=False,
            integrity_score=0.0,
            dissonance_ds=float("inf"),
            allowed_epsilon=allowed_eps,
            violated_policies=[reason],
            session_context=session_context,
            metrics={"error": reason}
        )
        self.aem.record({
            "admission_breach": True,
            "d_s": float("inf"),
            "violated_policies": [reason],
            "epsilon_used": allowed_eps,
            "epsilon": allowed_eps,
            "user_input": session_context.user_prompt,
            "audit_input": "Stage 2: Hardware Mask Containment Breach",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return result

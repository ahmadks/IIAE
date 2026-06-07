from __future__ import annotations
import os
import math
from datetime import datetime, timezone
from typing import Any, List, Optional, Dict, Tuple

from idicoc_core.api.schemas import NotaryAuditResult, SessionContext
from idicoc_core.dqe import ContextParser, InvarianceProjector
from idicoc_core.gating.hardware_mask import HardwareMask
from idicoc_core.exceptions import InvariantStateBreach
from idicoc_core.isg.graph_manager import PropertyGraph
from idicoc_core.isg.loader import parse_policy_line
from idicoc_core.dse.evaluator import DissonanceStateEvaluator
from idicoc_core.ctm.merkle_dag import (
    CustodialTraceManager,
    MerkleDAG,
    EnvHardwareSealer,
    FileCTMStorage,
)
from idicoc_core.ctm.wal_logger import WriteAheadLogger
from idicoc_core.utils.logger import get_logger
from idicoc_core.kernel.source.anchor import SourceAnchor

logger = get_logger("pipeline.orchestrator")


class AuditEntropyModule:
    """Audit Entropy Module (AEM) to track the audit history and rejections."""

    def __init__(self) -> None:
        self.trail: List[Dict[str, Any]] = []

        # AEM Accounting Counters (valores iniciales por defecto de 1.0 según especificación)
        self._y_total: float = 1.0  # Total signals processed by DQE
        self._y_valid: float = 1.0  # Signals validated/corrected by DQE

    def record(self, case: Dict[str, Any]) -> None:
        self.trail.append(case)
        total, valid, rejected = self.get_counters()
        self._y_total = float(total)
        self._y_valid = float(valid)

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        return self.trail

    def get_counters(self) -> Tuple[int, int, int]:
        total = len(self.trail)
        rejected = sum(1 for c in self.trail if c.get("admission_breach"))
        valid = total - rejected
        return total, valid, rejected

    @property
    def y_total(self) -> float:
        """Total signals processed by DQE (as float)"""
        return self._y_total

    @y_total.setter
    def y_total(self, value: float) -> None:
        self._y_total = float(value)

    @property
    def y_valid(self) -> float:
        """Signals validated/corrected by DQE (as float)"""
        return self._y_valid

    @y_valid.setter
    def y_valid(self, value: float) -> None:
        self._y_valid = float(value)


class AuditPipeline:
    def __init__(self, config: Any, llm_provider: Any = None):
        self.config = config
        self.llm_provider = llm_provider
        self.source_anchor = SourceAnchor() if getattr(config, "record_k_fingerprint", True) else None

        # 1. Initialize DQE (Context Parser & Invariance Projector)
        self.dqe = ContextParser(config)
        self.invariance_projector = InvarianceProjector(config, self.source_anchor)

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
                            timestamp=payload.get(
                                "timestamp", datetime.now(timezone.utc).isoformat()
                            ),
                            dissonance=payload.get("dissonance", 0.0),
                            transaction_id=tx_id,
                            violations=payload.get("violations"),
                            dissonance_components=payload.get("dissonance_components"),
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
                policy_id = policy_dict.get("policy_id") or policy_dict.get("id") or f"static_{idx}"
                if "embedding" not in policy_dict:
                    text_to_embed = (
                        policy_dict.get("text")
                        or policy_dict.get("description")
                        or str(policy_dict)
                    )
                    try:
                        policy_dict["embedding"] = embed_service.encode(
                            text_to_embed,
                            model_name=self.config.semantic_embedding_model,
                        ).tolist()
                    except Exception as e:
                        logger.warning(
                            f"Could not compute embedding for static policy {policy_id}: {e}"
                        )

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
        epsilon_override: Optional[float] = None,
        v_hat: Optional[Any] = None,
    ) -> NotaryAuditResult:
        # 1. DQE: Empaquetar el Estado Observable
        context = self.dqe.build_context(user_prompt, rag_context, v_hat=v_hat)

        if context.v_hat is None:
            try:
                # Si no se pasó v_hat, lo generamos proyectando el prompt original
                projected_vec = self.invariance_projector.project(user_prompt, self.isg)
                from idicoc_core.kernel.projection.invariant_state_generator import CanonicalState
                context.v_hat = CanonicalState(measure_vector=projected_vec, metadata={"origin": "execute_audit"})
            except InvariantStateBreach as e:
                # Si hay una violación de invarianza en el input original, se rechaza
                return self._build_hard_rejection(f"Input Invariance Containment Breach - {str(e)}", context)
            except Exception as e:
                logger.warning(f"Could not compute v_hat dynamically in execute_audit: {e}")

        # 2. Gating: Stage 2/3 (Hardware Mask & Domain Confinement)
        if not self.gating.is_hardware_contained(context):
            return self._build_hard_rejection("Stage 2: Hardware Mask Containment Breach", context)

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

        old_eps = self.dse.strategy.config.allowed_epsilon

        try:
            # 3. ISG: Cargar Invariantes
            graph = self.isg

            # 4. DSE: Evaluación Kantorovich-Lifted (Cálculo de D_s)
            if epsilon_override is not None:
                self.config.allowed_epsilon = epsilon_override

            d_s, violations, raw_metrics = self.dse.evaluate(llm_output, context, graph)
            d_s = float(d_s)

            # Umbral efectivo = base_tolerance + epsilon (permite omisiones suaves)
            allowed_eps = float(
                epsilon_override if epsilon_override is not None else self.config.allowed_epsilon
            )
            effective_threshold = self.config.correction_base_tolerance + allowed_eps

            spsa_corrected = False
            original_d_s = d_s

            # Check for SPSA capability
            y_vec = raw_metrics.get("y_vector")
            v_hat_vec = None
            if context.v_hat is not None and hasattr(context.v_hat, "semantic_vector"):
                v_hat_vec = context.v_hat.semantic_vector

            has_spsa_capability = (y_vec is not None and v_hat_vec is not None)

            # Gray Zone Optimization check using SPSA
            if has_spsa_capability and (self.config.diss_threshold_green < d_s < self.config.diss_threshold_red):
                import numpy as np
                context_embs = raw_metrics.get("context_embeddings")
                best_z, best_loss = self.dse.project_spsa(
                    y_vec=y_vec,
                    v_hat_vec=v_hat_vec,
                    const_metrics=raw_metrics,
                    context_embs=context_embs
                )
                
                if best_loss < d_s:
                    d_s = best_loss
                    raw_metrics["d_s"] = best_loss
                    
                    dist = float(np.linalg.norm(best_z - v_hat_vec))
                    raw_metrics["d_1"] = float(np.clip(dist / 2.0, 0.0, 1.0))
                    raw_metrics["y_vector"] = best_z
                    
                    spsa_corrected = True
                    
                    if not context.metadata:
                        context.metadata = {}
                    context.metadata["spsa_corrected"] = True
                    context.metadata["spsa_original_dissonance"] = original_d_s
                    raw_metrics["spsa_corrected"] = True
                    raw_metrics["spsa_original_dissonance"] = original_d_s

                    # If converged to compliance, clear violations
                    if d_s <= effective_threshold:
                        violations = []
                        raw_metrics["violated_policies"] = []

            is_admitted = bool(d_s <= effective_threshold)

            # Enforce hard halt and SPSA convergence exceptions
            if math.isinf(d_s):
                raise InvariantStateBreach(
                    message="Hard Policy Violation: Infinite dissonance detected.",
                    invalid_state=llm_output,
                    origin="execute_audit.hard_violation"
                )

            if has_spsa_capability:
                # Red Zone breach (Integrity Breach / Hard Halt)
                if math.isinf(d_s):
                    raise InvariantStateBreach(
                        message="Post-generation Red Zone Integrity Breach: Infinite dissonance detected.",
                        invalid_state=llm_output,
                        origin="execute_audit.evaluate_red_zone"
                    )
                # SPSA convergence failure
                elif (self.config.diss_threshold_green < original_d_s < self.config.diss_threshold_red) and not is_admitted:
                    raise InvariantStateBreach(
                        message=f"Post-generation SPSA audit failed to converge below acceptable threshold {effective_threshold:.3f}. Dissonance = {d_s:.3f}",
                        invalid_state=llm_output,
                        origin="execute_audit.spsa_check"
                    )


            # Restore original config epsilon
            self.config.allowed_epsilon = old_eps


            # 5. CTM: Efecto Secundario Criptográfico (Silent Emission)
            if self.config.ctm_mode == "full":
                tx_id = f"tx_{hash(llm_output)}_{int(datetime.now(timezone.utc).timestamp())}"
                timestamp = datetime.now(timezone.utc).isoformat()
                wal_payload = {
                    "user_prompt": user_prompt,
                    "rag_context": rag_context,
                    "output": llm_output,
                    "dissonance": d_s,
                    "is_admitted": is_admitted,
                    "violations": violations,
                    "timestamp": timestamp,
                }
                if spsa_corrected:
                    wal_payload["spsa_corrected"] = True
                    wal_payload["spsa_original_dissonance"] = original_d_s
                    
                if self.source_anchor:
                    wal_payload["k_fingerprint"] = self.source_anchor.fingerprint

                # Check for distribution to include in WAL payload
                dist_val = None
                if isinstance(context, dict):
                    dist_val = context.get("distribution") or context.get("metadata", {}).get(
                        "distribution"
                    )
                else:
                    dist_val = getattr(context, "distribution", None) or (
                        context.metadata or {}
                    ).get("distribution")

                if dist_val is None:
                    try:
                        if isinstance(llm_output, str) and (
                            llm_output.startswith("[") or "array" in llm_output
                        ):
                            import ast

                            parsed = ast.literal_eval(llm_output)
                            if isinstance(parsed, (list, tuple)):
                                dist_val = list(parsed)
                    except Exception:
                        pass

                if dist_val is not None:
                    if hasattr(dist_val, "tolist"):
                        dist_val = dist_val.tolist()
                    wal_payload["distribution"] = dist_val

                dissonance_components = {
                    "d_axiomatic": float(raw_metrics.get("d_logic", d_s)),
                    "d_context": float(raw_metrics.get("d_context", 0.0)),
                }
                wal_payload["dissonance_components"] = dissonance_components

                self.wal.write(tx_id, wal_payload)
                try:
                    self.ctm.commit_trace(
                        context,
                        llm_output,
                        d_s,
                        is_admitted,
                        violations,
                        transaction_id=tx_id,
                        timestamp=timestamp,
                        dissonance_components=dissonance_components,
                        k_fingerprint=self.source_anchor.fingerprint if self.source_anchor else None,
                    )
                    self.wal.mark_completed(tx_id)
                except Exception as exc:
                    logger.error(f"CTM commit failure: {exc}")

            # 6. Mapeo de Terminalidad Coálgebraica:
            integrity_score = (
                0.0 if math.isinf(d_s) or math.isnan(d_s) else float(max(0.0, 1.0 - d_s))
            )

            result = NotaryAuditResult(
                is_admitted=is_admitted,
                integrity_score=integrity_score,
                dissonance_ds=d_s,
                allowed_epsilon=effective_threshold,
                violated_policies=violations,
                session_context=context,
                metrics=raw_metrics,
            )

            # Record in AEM
            self.aem.record(
                {
                    "admission_breach": not is_admitted,
                    "d_s": d_s,
                    "violated_policies": violations,
                    "epsilon_used": effective_threshold,
                    "epsilon": effective_threshold,
                    "user_input": user_prompt,
                    "audit_input": llm_output,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

            return result
        except InvariantStateBreach as e:
            logger.warning(f"Post-generation audit aborted due to InvariantStateBreach: {e}")
            self.config.allowed_epsilon = old_eps
            
            # Construct a hard rejection result that preserves violations and metrics
            if 'violations' not in locals() or not violations:
                local_violations = [f"[CRITICAL_HARD_HALT] {str(e)}"]
            else:
                local_violations = list(violations)
                local_violations.append(f"[CRITICAL_HARD_HALT] {str(e)}")
                
            if 'raw_metrics' not in locals() or not raw_metrics:
                local_metrics = {
                    "d_s": float("inf"),
                    "error": str(e),
                    "violated_policies": local_violations,
                }
            else:
                local_metrics = dict(raw_metrics)
                local_metrics["d_s"] = float("inf")
                local_metrics["violated_policies"] = local_violations
                local_metrics["error"] = str(e)

            result = NotaryAuditResult(
                is_admitted=False,
                integrity_score=0.0,
                dissonance_ds=float("inf"),
                allowed_epsilon=effective_threshold if 'effective_threshold' in locals() else self.config.correction_base_tolerance,
                violated_policies=local_violations,
                session_context=context,
                metrics=local_metrics,
            )

            # Record in AEM
            self.aem.record(
                {
                    "admission_breach": True,
                    "d_s": float("inf"),
                    "violated_policies": local_violations,
                    "epsilon_used": effective_threshold if 'effective_threshold' in locals() else self.config.correction_base_tolerance,
                    "epsilon": effective_threshold if 'effective_threshold' in locals() else self.config.correction_base_tolerance,
                    "user_input": user_prompt,
                    "audit_input": llm_output,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            return result

        finally:
            if added_dynamic_ids:
                for ax_id in added_dynamic_ids:
                    self.isg.nodes.pop(ax_id, None)
                self.isg.detect_conflicts()


    def generate(
        self,
        user_prompt: str,
        rag_context: str | List[str],
        context_policies: Optional[List[Any]] = None,
        epsilon_override: Optional[float] = None,
        **kwargs
    ) -> Tuple[str, NotaryAuditResult]:
        """
        Generates LLM output under containment using the InvarianceProjector,
        and then runs post-audit verification on the response.
        """
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

        if isinstance(rag_context, list):
            rag_str = "\n".join(rag_context)
        else:
            rag_str = rag_context or ""

        try:
            # 1. Proyección de Input (Contención Preventiva)
            # Evalúa consistencia lógica de la entrada y proyecta su vector
            try:
                projected_vec = self.invariance_projector.project(user_prompt, self.isg)
                from idicoc_core.kernel.projection.invariant_state_generator import CanonicalState
                v_hat = CanonicalState(measure_vector=projected_vec, metadata={"origin": "invariance_projector"})
            except InvariantStateBreach as e:
                session_context = self.dqe.build_context(user_prompt, rag_str)
                reject_reason = f"Stage 1: Input Invariance Containment Breach - {str(e)}"
                return "", self._build_hard_rejection(reject_reason, session_context)

            # 2. Generación con Prompt Limpio (Cero Prompting)
            if not self.llm_provider:
                raise ValueError("No llm_provider configured for generate().")

            if rag_str:
                clean_prompt = f"CONTEXT:\n{rag_str}\n\nUSER REQUEST:\n{user_prompt}"
            else:
                clean_prompt = user_prompt

            llm_output = self.llm_provider.generate(clean_prompt, **kwargs)

            # 3. Auditoría (Post-verificación reactiva)
            audit_result = self.execute_audit(
                user_prompt=user_prompt,
                rag_context=rag_str,
                llm_output=llm_output,
                context_policies=None,
                epsilon_override=epsilon_override,
                v_hat=v_hat,
            )

            if not audit_result.is_admitted and math.isinf(audit_result.dissonance_ds):
                return "", audit_result

            return llm_output, audit_result

        finally:
            if added_dynamic_ids:
                for ax_id in added_dynamic_ids:
                    self.isg.nodes.pop(ax_id, None)
                self.isg.detect_conflicts()

    def _build_rejection(self, reason: str, session_context: SessionContext) -> NotaryAuditResult:
        allowed_eps = self.config.allowed_epsilon
        effective_threshold = self.config.correction_base_tolerance + allowed_eps
        result = NotaryAuditResult(
            is_admitted=False,
            integrity_score=0.0,
            dissonance_ds=float("inf"),
            allowed_epsilon=effective_threshold,
            violated_policies=[reason],
            session_context=session_context,
            metrics={"error": reason},
        )
        self.aem.record(
            {
                "admission_breach": True,
                "d_s": float("inf"),
                "violated_policies": [reason],
                "epsilon_used": effective_threshold,
                "epsilon": effective_threshold,
                "user_input": session_context.user_prompt,
                "audit_input": "Stage 2: Hardware Mask Containment Breach",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return result

    def _build_hard_rejection(
        self, reason: str, session_context: SessionContext
    ) -> NotaryAuditResult:
        return self._build_rejection(reason, session_context)

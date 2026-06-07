from __future__ import annotations
import os
import math
from datetime import datetime, timezone
from typing import Any, List, Optional, Dict, Tuple

from idicoc_core.api.schemas import NotaryAuditResult, SessionContext
from idicoc_core.dqe.context_parser import ContextParser
from idicoc_core.dqe.invariance_projector import InvarianceProjector
from idicoc_core.exceptions import InvariantStateBreach
from idicoc_core.gating.hardware_mask import HardwareMask
from idicoc_core.isg.graph_manager import PropertyGraph
from idicoc_core.isg.loader import parse_policy_line
from idicoc_core.kernel.projection.invariant_state_generator import CanonicalState
from idicoc_core.dse.evaluator import DissonanceStateEvaluator
from idicoc_core.ctm.merkle_dag import (
    CustodialTraceManager,
    MerkleDAG,
    EnvHardwareSealer,
    FileCTMStorage,
)
from idicoc_core.ctm.wal_logger import WriteAheadLogger
from idicoc_core.utils.logger import get_logger

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

    @staticmethod
    def _normalize_rag_context(rag_context: Any) -> str:
        if rag_context is None:
            return ""
        if isinstance(rag_context, (list, tuple)):
            return "\n".join(str(item).strip() for item in rag_context if str(item).strip())
        return str(rag_context or "")

    def _build_generation_prompt(self, user_prompt: str, rag_context: str) -> str:
        prompt_parts = [user_prompt.strip()]
        if rag_context.strip():
            prompt_parts.append("CONTEXT:\n" + rag_context.strip())
        return "\n\n".join(prompt_parts)

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

    def _add_dynamic_policies(self, context_policies: Optional[List[Any]]) -> List[str]:
        added_dynamic_ids: List[str] = []
        if not context_policies:
            return added_dynamic_ids

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

        return added_dynamic_ids

    def _attempt_spsa_correction(
        self,
        llm_output: str,
        session_context: SessionContext,
        raw_metrics: Dict[str, Any],
        effective_threshold: float,
    ) -> Optional[float]:
        try:
            from idicoc_core.utils.string_utils import StringUtils

            y_vec = StringUtils.to_vector(
                llm_output,
                model_name=self.config.semantic_embedding_model,
            )
            v_hat = getattr(session_context, "v_hat", None)
            if v_hat is None:
                return None

            v_hat_vec = getattr(v_hat, "semantic_vector", v_hat)
            if v_hat_vec is None:
                return None

            corrected_vector, corrected_loss, history = self.dse.project_spsa(
                y_vec,
                v_hat_vec,
                raw_metrics,
                context_embs=raw_metrics.get("context_embeddings", []),
            )

            raw_metrics["spsa_history"] = history
            return float(corrected_loss)
        except Exception as exc:
            logger.error(f"Error during SPSA correction: {exc}", exc_info=True)
            raw_metrics["spsa_error"] = str(exc)
            return None

    def _should_apply_spsa(self, d_s: float, raw_metrics: Dict[str, Any]) -> bool:
        d1 = float(raw_metrics.get("d_1", 0.0))
        d2 = float(raw_metrics.get("d_2", 0.0))
        d3 = float(raw_metrics.get("d_3", 0.0))

        # Do not attempt SPSA when any discrete violation exists.
        if d2 > 0.0 or d3 > 0.0:
            return False
        if d_s == float("inf"):
            return False

        # SPSA is only allowed in the gray band for d1 and d_s.
        in_d1_gray = self.config.diss_threshold_green < d1 <= self.config.diss_threshold_red
        in_ds_gray = self.config.diss_threshold_green < d_s <= self.config.diss_threshold_red
        return in_d1_gray and in_ds_gray

    def execute_audit(
        self,
        user_prompt: str,
        rag_context: Any,
        llm_output: str,
        context_policies: Optional[List[Any]] = None,
        epsilon_override: Optional[float] = None,
        session_context: Optional[SessionContext] = None,
    ) -> NotaryAuditResult:
        # 1. DQE: Empaquetar el Estado Observable
        if session_context is None:
            context = self.dqe.build_context(user_prompt, rag_context)
        else:
            context = session_context

        # 2. Gating: Stage 2/3 (Hardware Mask & Domain Confinement)
        if not self.gating.is_hardware_contained(context):
            return self._build_hard_rejection("Stage 2: Hardware Mask Containment Breach", context)

        # Dynamic policies management
        added_dynamic_ids = self._add_dynamic_policies(context_policies)

        try:
            # 3. ISG: Cargar Invariantes
            graph = self.isg

            # 4. DSE: Evaluación Kantorovich-Lifted (Cálculo de D_s)
            old_eps = self.dse.strategy.config.allowed_epsilon
            if epsilon_override is not None:
                self.config.allowed_epsilon = epsilon_override

            d_s, violations, raw_metrics = self.dse.evaluate(llm_output, context, graph)
            d_s = float(d_s)
            if d_s == float("inf") and "[CRITICAL_HARD_HALT]" not in violations:
                violations.insert(0, "[CRITICAL_HARD_HALT] Hard policy breach detected.")

            # Umbral efectivo = base_tolerance + epsilon (permite omisiones suaves)
            allowed_eps = float(
                epsilon_override if epsilon_override is not None else self.config.allowed_epsilon
            )
            effective_threshold = self.config.correction_base_tolerance + allowed_eps
            is_admitted = bool(d_s <= effective_threshold)

            if raw_metrics.get("d_2", 0.0) > 0.0 or raw_metrics.get("d_3", 0.0) > 0.0:
                logger.error(
                    "[DSE] Bloqueo inmediato por violación discreta: d_2=%s d_3=%s",
                    raw_metrics.get("d_2", 0.0),
                    raw_metrics.get("d_3", 0.0),
                )
                d_s = float("inf")
                is_admitted = False
                if "[CRITICAL_HARD_HALT] Violación discreta d_2/d_3 detectada." not in violations:
                    violations.append("[CRITICAL_HARD_HALT] Violación discreta d_2/d_3 detectada.")
            elif (
                self._should_apply_spsa(d_s, raw_metrics)
                and getattr(context, "v_hat", None) is not None
            ):
                corrected_d_s = self._attempt_spsa_correction(
                    llm_output,
                    context,
                    raw_metrics,
                    effective_threshold,
                )
                if corrected_d_s is not None:
                    raw_metrics["spsa_original_dissonance"] = float(d_s)
                    raw_metrics["spsa_corrected_dissonance"] = float(corrected_d_s)
                    raw_metrics["spsa_corrected"] = corrected_d_s <= effective_threshold

                    if corrected_d_s <= effective_threshold:
                        d_s = float(corrected_d_s)
                        is_admitted = True
                        logger.info(
                            "[DSE] SPSA corregido con éxito: d_s_original=%s -> d_s_corregido=%s",
                            raw_metrics["spsa_original_dissonance"],
                            corrected_d_s,
                        )
                    else:
                        d_s = float("inf")
                        is_admitted = False
                        if "[CRITICAL_HARD_HALT] SPSA convergence failed." not in violations:
                            violations.append("[CRITICAL_HARD_HALT] SPSA convergence failed.")
                        logger.warning(
                            "[DSE] SPSA no convergió. corrected_d_s=%s > threshold=%s",
                            corrected_d_s,
                            effective_threshold,
                        )
                else:
                    d_s = float("inf")
                    is_admitted = False
                    if "[CRITICAL_HARD_HALT] No se pudo ejecutar SPSA." not in violations:
                        violations.append("[CRITICAL_HARD_HALT] No se pudo ejecutar SPSA.")
            elif is_admitted:
                logger.info(
                    "[DSE] Señal admitida sin corrección. d_s=%s <= effective_threshold=%s",
                    d_s,
                    effective_threshold,
                )
            else:
                logger.error(
                    "[DSE] Rechazo sin corrección SPSA. d_1=%s d_2=%s d_3=%s d_s=%s",
                    raw_metrics.get("d_1", 0.0),
                    raw_metrics.get("d_2", 0.0),
                    raw_metrics.get("d_3", 0.0),
                    d_s,
                )
                d_s = float("inf")
                is_admitted = False
                if (
                    "[CRITICAL_HARD_HALT] Rechazo sin SPSA por zona roja o violaciones discreta."
                    not in violations
                ):
                    violations.append(
                        "[CRITICAL_HARD_HALT] Rechazo sin SPSA por zona roja o violaciones discreta."
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
        finally:
            if added_dynamic_ids:
                for ax_id in added_dynamic_ids:
                    self.isg.nodes.pop(ax_id, None)
                self.isg.detect_conflicts()

    def generate(
        self,
        user_prompt: str,
        rag_context: Any,
        context_policies: Optional[List[Any]] = None,
        epsilon_override: Optional[float] = None,
        **kwargs,
    ) -> Tuple[str, NotaryAuditResult]:
        if self.llm_provider is None:
            raise ValueError("LLM provider is required for generation.")

        normalized_rag = self._normalize_rag_context(rag_context)
        session_context = self.dqe.build_context(user_prompt, normalized_rag)
        added_dynamic_ids = self._add_dynamic_policies(context_policies)

        try:
            # Input projection / containment gate
            try:
                projected_vector = InvarianceProjector(self.config).project(user_prompt, self.isg)
                session_context.v_hat = CanonicalState(
                    measure_vector=projected_vector,
                    metadata={"source": "input_projection"},
                )
            except InvariantStateBreach as exc:
                return "", self._build_hard_rejection(str(exc), session_context)
            except Exception as exc:
                logger.error("Input projection failed: %s", exc, exc_info=True)
                return "", self._build_hard_rejection(
                    "Input projection failed during generation.", session_context
                )

            # Do not inject hidden system prompts or policy clauses into the LLM request.
            prompt = self._build_generation_prompt(user_prompt, normalized_rag)
            llm_output = self.llm_provider.generate(prompt, **kwargs)

            audit_result = self.execute_audit(
                user_prompt=user_prompt,
                rag_context=normalized_rag,
                llm_output=llm_output,
                context_policies=None,
                epsilon_override=epsilon_override,
                session_context=session_context,
            )
            if not audit_result.is_admitted:
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

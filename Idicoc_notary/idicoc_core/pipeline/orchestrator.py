from __future__ import annotations
import math
import time
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
from idicoc_core.dse.spsa import SPSACorrector
from idicoc_core.dse.aem import AuditEntropyModule
from idicoc_core.pipeline.ctm_orchestration import CTMOrchestrator
from idicoc_core.utils.logger import get_logger
from idicoc_core.utils.string_utils import StringUtils

logger = get_logger("pipeline.orchestrator")


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
        self.spsa = SPSACorrector(config)

        # 5. Initialize CTM & WAL orchestrator
        self.ctm_orchestrator = CTMOrchestrator(config)

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

        t_start = time.perf_counter()
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
        finally:
            t_elapsed = time.perf_counter() - t_start
            logger.info(
                "[TIMING] Dynamic policies added: %d policies, %.3f sec",
                len(added_dynamic_ids),
                t_elapsed,
            )

        return added_dynamic_ids

    def _attempt_spsa_correction(
        self,
        llm_output: str,
        session_context: SessionContext,
        raw_metrics: Dict[str, Any],
        effective_threshold: float,
    ) -> Optional[float]:
        """
        Delegate to SPSACorrector to attempt dissonance correction.
        Returns corrected dissonance or None if correction fails.
        """
        try:
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

            return self.spsa.attempt_correction(
                llm_output, y_vec, v_hat_vec, raw_metrics, effective_threshold
            )

        except Exception as exc:
            logger.error(f"Error during SPSA correction: {exc}", exc_info=True)
            raw_metrics["spsa_error"] = str(exc)
            return None

    def execute_audit(
        self,
        user_prompt: str,
        rag_context: Any,
        llm_output: str,
        context_policies: Optional[List[Any]] = None,
        epsilon_override: Optional[float] = None,
        session_context: Optional[SessionContext] = None,
    ) -> NotaryAuditResult:
        t_audit_start = time.perf_counter()
        logger.info("[TIMING] execute_audit START")

        # 1. DQE: Empaquetar el Estado Observable
        t_dqe_start = time.perf_counter()
        if session_context is None:
            context = self.dqe.build_context(user_prompt, rag_context)
        else:
            context = session_context
        t_dqe_elapsed = time.perf_counter() - t_dqe_start
        logger.info("[TIMING] DQE context build: %.3f sec", t_dqe_elapsed)

        # 2. Gating: Stage 2/3 (Hardware Mask & Domain Confinement)
        t_gating_start = time.perf_counter()
        if not self.gating.is_hardware_contained(context):
            t_gating_elapsed = time.perf_counter() - t_gating_start
            logger.warning("[TIMING] Gating rejection after %.3f sec", t_gating_elapsed)
            return self._build_hard_rejection("Stage 2: Hardware Mask Containment Breach", context)
        t_gating_elapsed = time.perf_counter() - t_gating_start
        logger.info("[TIMING] Gating check: %.3f sec", t_gating_elapsed)

        # Dynamic policies management
        added_dynamic_ids = self._add_dynamic_policies(context_policies)

        try:
            # 3. ISG: Cargar Invariantes
            graph = self.isg

            # 4. DSE: Evaluación Kantorovich-Lifted (Cálculo de D_s)
            t_dse_start = time.perf_counter()
            old_eps = self.dse.strategy.config.allowed_epsilon
            if epsilon_override is not None:
                self.config.allowed_epsilon = epsilon_override

            d_s, violations, raw_metrics = self.dse.evaluate(llm_output, context, graph)
            t_dse_elapsed = time.perf_counter() - t_dse_start
            logger.info("[TIMING] DSE evaluate: %.3f sec | d_s=%.6f", t_dse_elapsed, float(d_s))
            d_s = float(d_s)
            if d_s == float("inf") and "[CRITICAL_HARD_HALT]" not in violations:
                violations.append("[CRITICAL_HARD_HALT] Hard policy breach detected.")

            # Umbral efectivo = base_tolerance + epsilon (permite omisiones suaves)
            allowed_eps = float(
                epsilon_override if epsilon_override is not None else self.config.allowed_epsilon
            )
            effective_threshold = self.config.correction_base_tolerance + allowed_eps
            is_admitted = bool(d_s <= effective_threshold)

            # Attempt SPSA correction if applicable
            if (
                self.spsa.should_apply_correction(d_s, raw_metrics)
                and getattr(context, "v_hat", None) is not None
            ):
                logger.info("[TIMING] Attempting SPSA correction...")
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
                is_admitted = False

            # Restore original config epsilon
            self.config.allowed_epsilon = old_eps

            # 5. CTM: Efecto Secundario Criptográfico (Silent Emission)
            self.ctm_orchestrator.commit_audit_trace(
                user_prompt=user_prompt,
                rag_context=self._normalize_rag_context(rag_context),
                llm_output=llm_output,
                session_context=context,
                d_s=d_s,
                is_admitted=is_admitted,
                violations=violations,
                raw_metrics=raw_metrics,
            )

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

            t_audit_total = time.perf_counter() - t_audit_start
            logger.info(
                "[TIMING] execute_audit TOTAL: %.3f sec | admitted=%s | d_s=%.6f",
                t_audit_total,
                is_admitted,
                float(d_s),
            )
            raw_metrics["audit_duration_sec"] = t_audit_total
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
        t_generate_start = time.perf_counter()
        logger.info("[TIMING] generate START")

        if self.llm_provider is None:
            raise ValueError("LLM provider is required for generation.")

        t_rag_start = time.perf_counter()
        normalized_rag = self._normalize_rag_context(rag_context)
        session_context = self.dqe.build_context(user_prompt, normalized_rag)
        t_rag_elapsed = time.perf_counter() - t_rag_start
        logger.info("[TIMING] RAG context normalization: %.3f sec", t_rag_elapsed)

        added_dynamic_ids = self._add_dynamic_policies(context_policies)

        try:
            # Input projection / containment gate
            try:
                t_proj_start = time.perf_counter()
                projected_vector = InvarianceProjector(self.config).project(user_prompt, self.isg)
                t_proj_elapsed = time.perf_counter() - t_proj_start
                logger.info("[TIMING] Input projection: %.3f sec", t_proj_elapsed)

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
            t_llm_start = time.perf_counter()
            llm_output = self.llm_provider.generate(prompt, **kwargs)
            t_llm_elapsed = time.perf_counter() - t_llm_start
            logger.info(
                "[TIMING] LLM generation: %.3f sec | output_len=%d chars",
                t_llm_elapsed,
                len(llm_output) if llm_output else 0,
            )

            audit_result = self.execute_audit(
                user_prompt=user_prompt,
                rag_context=normalized_rag,
                llm_output=llm_output,
                context_policies=None,
                epsilon_override=epsilon_override,
                session_context=session_context,
            )
            if not audit_result.is_admitted:
                t_generate_total = time.perf_counter() - t_generate_start
                logger.warning(
                    "[TIMING] generate REJECTED: %.3f sec total",
                    t_generate_total,
                )
                return "", audit_result

            t_generate_total = time.perf_counter() - t_generate_start
            logger.info(
                "[TIMING] generate COMPLETE: %.3f sec total | llm=%.3f sec",
                t_generate_total,
                t_llm_elapsed,
            )
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

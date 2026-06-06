from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import threading
from idicoc_notary_core.kernel.custody.merkle_dag import (
    CustodialTraceManager,
    EnvHardwareSealer,
    MerkleDAG,
)
from idicoc_notary_core.kernel.dse.dse import PolicyExtractor
from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph
from idicoc_notary_core.kernel.manifold.cmc import ManifoldConstructor
from idicoc_notary_core.kernel.projection import InvariantStateGenerator
from idicoc_notary_core.kernel.verification.registry import ProjectionRegistry
from idicoc_notary_core.kernel.verification.verifier import InvariantVerifier
from idicoc_notary_core.utils.logger import get_logger
from idicoc_notary_core.utils.hashing import canonical_json, sha256_hex
from idicoc_notary_core.audit.graph.loader.file_loader import parse_policy_line

from idicoc_notary_core.base import CanonicalStateDTO
from .persistence.file_backend import FileCTMStorage
from .config import AuditConfig
from .exceptions import WrapperInitializationError
from .ctm_client import KernelCustodyClient
from .dse import (
    DissonanceStrategy as DissonanceStrategyProtocol,
    StructuralDissonanceStrategy,
)
from .graph.cache import GraphCache
from .aem import AuditEntropyModule


class IDICOCPipeline:
    """Orquestador lineal del auditor que ejecuta cada etapa del pipeline."""

    def __init__(
        self,
        config: AuditConfig,
        graph_cache: Optional[GraphCache] = None,
        llm_provider: Any = None,
    ) -> None:
        self.config = config
        self.llm_provider = llm_provider
        # If llm_provider exposes an embedding adapter, prefer it for embedding computations
        try:
            if llm_provider is not None and hasattr(llm_provider, "embedding_provider"):
                self.config.embedding_provider = getattr(llm_provider, "embedding_provider")
        except Exception:
            pass
        self.graph_cache = graph_cache
        self.graph = PropertyGraph(embedding_signature=self.config.embedding_signature)
        self.logger = get_logger("audit_flow.pipeline")
        self.aem = AuditEntropyModule()
        self._aem_lock = threading.Lock()

        # Selección dinámica y configurable de backend de almacenamiento para CTM
        backend_type = getattr(self.config, "ctm_storage_backend", "file")
        ctm_storage: Any
        if isinstance(backend_type, str):
            backend_type_lower = backend_type.lower()
            if backend_type_lower == "file":
                ctm_storage = FileCTMStorage(
                    self.config.ctm_nodes_path,
                    self.config.ctm_root_path,
                )
            elif backend_type_lower in ("postgres", "dynamodb", "qldb"):
                raise ValueError(
                    f"Backend de almacenamiento CTM '{backend_type}' ya no está soportado en la arquitectura."
                )
            else:
                raise ValueError(f"Backend de almacenamiento CTM no soportado: {backend_type}")
        else:
            if isinstance(backend_type, type):
                kwargs = getattr(self.config, "ctm_storage_kwargs", {})
                ctm_storage = backend_type(**kwargs)
            else:
                ctm_storage = backend_type

        self.registry = ProjectionRegistry()
        self.isg = InvariantStateGenerator(
            anchor=None,
            registry=self.registry,
            config=self.config,
        )
        self.verifier = InvariantVerifier(None)
        self.dse = PolicyExtractor(self.graph, self.config)
        self.dissonance_strategy = self._create_dissonance_strategy()
        self.dqe = self.dissonance_strategy
        self.cmc = ManifoldConstructor(dqe=self.dqe)
        self.ctm = CustodialTraceManager(
            dag=MerkleDAG(
                sealer=EnvHardwareSealer(
                    key_env=self.config.hardware_key_env_var,
                    require_key=self.config.require_hardware_seal,
                ),
                storage_backend=ctm_storage,
            )
        )

        genesis_metadata: dict[str, Any] = {
            "instance_name": self.config.instance_name,
            "ctm_mode": self.config.ctm_mode,
            "rigidity_epsilon": self.config.rigidity_epsilon,
            "lambda_weights": [
                self.dqe.lambda_0,
                self.dqe.lambda_1,
                self.dqe.lambda_2,
                self.dqe.lambda_3,
                self.dqe.lambda_4,
                self.dqe.lambda_5,
                self.dqe.lambda_6,
            ],
            "embedding_model_signature": self.config.embedding_signature,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.ctm.initialize_genesis(
            genesis_metadata,
            timestamp=genesis_metadata["timestamp"],
        )

        self.kernel_client = (
            KernelCustodyClient(ctm=self.ctm) if self.config.ctm_mode == "full" else None
        )

        # Inicializar Write-Ahead Logger para resiliencia Enterprise
        import os

        wal_path = self.config.ctm_wal_path
        if not wal_path:
            wal_path = os.path.join(
                os.path.dirname(self.config.ctm_nodes_path or "."), "ctm_wal.log"
            )
        from .persistence.ctm_wal import WriteAheadLogger

        self.wal = WriteAheadLogger(wal_path)

        # Reconciliación automática al arranque
        pending_txs = self.wal.recover_pending_transactions()
        if pending_txs:
            self.logger.warning(
                f"Se detectaron {len(pending_txs)} transacciones pendientes de confirmación en el WAL local. "
                "Iniciando reconciliación automática..."
            )
            try:
                reconciled = self.reconcile_wal()
                self.logger.info(
                    f"Reconciliación del WAL completada: {reconciled}/{len(pending_txs)} transacciones recuperadas."
                )
            except Exception as e:
                self.logger.error(f"Error durante la reconciliación del WAL: {e}")

        self._initialized = False
        self.initialize()

    def _create_dissonance_strategy(self) -> DissonanceStrategyProtocol:
        return self.config.dissonance_strategy(config=self.config)

    def initialize(self) -> None:
        self._load_initial_policies()
        self._initialized = True

    def _load_initial_policies(self) -> None:
        """Carga y procesa politicas estáticos, usando caché si está disponible."""
        if not self.config.policy_loader:
            return

        # 1. Intentar recuperar desde caché
        tenant_id = self.config.client_id
        policies_data = self.config.policy_loader.load_policies()

        # Calcular hash canónico de los datos
        content_hash = sha256_hex(canonical_json(policies_data))
        cache_key = f"property_graph:{tenant_id}:{content_hash}"

        if self.graph_cache:
            cached_graph = self.graph_cache.get(cache_key)
            if cached_graph:
                # Validar la firma del embedding
                if cached_graph.embedding_signature == self.config.embedding_signature:
                    self.graph = cached_graph
                    self.logger.info("PropertyGraph cargado desde caché exitosamente.")
                    return
                else:
                    msg = f"Firma de embedding en caché ({cached_graph.embedding_signature}) no coincide con la actual ({self.config.embedding_signature})."
                    if self.config.strict_embedding_signature:
                        raise RuntimeError(f"Strict mode: {msg}")
                    else:
                        self.logger.warning(f"{msg} Invalidando caché y recalculando.")

        # 2. Si no hay caché o fue invalidada, construimos el grafo
        from idicoc_notary_core.utils.embedding_service import EmbeddingService

        embed_service = EmbeddingService()

        # Crear nuevo grafo
        self.graph = PropertyGraph(embedding_signature=self.config.embedding_signature)

        for idx, policy_dict in enumerate(policies_data):
            policy_id = (
                policy_dict.get("policy_id") or policy_dict.get("id") or f"policy_loaded_{idx}"
            )

            # Precomputar embedding
            if "embedding" not in policy_dict:
                text_to_embed = (
                    policy_dict.get("text") or policy_dict.get("description") or str(policy_dict)
                )
                try:
                    vec = embed_service.encode(
                        text_to_embed,
                        model_name=self.config.semantic_embedding_model,
                    )
                    policy_dict["embedding"] = vec.tolist()
                except Exception as e:
                    self.logger.warning(f"No se pudo precomputar embedding para {policy_id}: {e}")

            self.graph.add_policy(policy_id, policy_dict)

        self.graph.detect_conflicts()
        self.logger.info(f"Loaded {len(policies_data)} static policies into the PropertyGraph.")

        # 3. Guardar en caché si está habilitada
        if self.graph_cache:
            self.graph_cache.set(cache_key, self.graph)
            self.logger.info("PropertyGraph guardado en caché.")

    def execute(
        self,
        audit_input: Any,
        context_input: Optional[List[str]] = None,
        context_policies: Optional[List[str | Dict[str, Any]]] = None,
        user_input: str | None = None,
        epsilon_override: float | None = None,
        trace_input: str = "",
        client_id: str | None = None,
    ) -> Dict[str, Any]:
        epsilon_used = (
            epsilon_override if epsilon_override is not None else self.config.rigidity_epsilon
        )
        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Validación de entrada mínima
        if audit_input is None or (isinstance(audit_input, str) and not audit_input.strip()):
            return self._build_fallback_result(
                "empty_input",
                "Entrada vacía o nula",
                epsilon_used,
                trace_input,
                client_id,
                context_policies,
                context_input,
            )

        added_dynamic_ids = []
        try:
            context_chunks = context_input or []
            all_policies = list(context_policies) if context_policies else []

            # Inyectar temporalmente politicas de contexto dinámicos al PropertyGraph
            if context_policies:
                from idicoc_notary_core.utils.embedding_service import EmbeddingService

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
                        policy_dict["source"] = f"dynamic_policy_{idx+1}"
                        policy_dict["source_text"] = policy_dict["text"]
                    else:
                        continue

                    if "embedding" not in policy_dict:
                        raw_text = (
                            policy_dict.get("text") or policy_dict.get("description") or policy_dict
                        )
                        text_to_embed = str(raw_text)
                        try:
                            vec = embed_service.encode(
                                text_to_embed,
                                model_name=self.config.semantic_embedding_model,
                            )
                            policy_dict["embedding"] = vec.tolist()
                        except Exception as e:
                            self.logger.warning(
                                f"No se pudo precomputar embedding para dynamic policy {policy_id}: {e}"
                            )

                    self.graph.add_policy(policy_id, policy_dict)
                    added_dynamic_ids.append(policy_id)

                self.graph.detect_conflicts()

            # 2. ISG
            V_hat = self.isg.generate(audit_input)

            # 3. DSE (Solo lectura)
            # El PropertyGraph es inmutable en tiempo de ejecución.
            # Los politicas fijos ya se cargaron. El contexto dinámico se pasará
            # a la estrategia para su evaluación temporal pero no se guardará en el grafo.

            # 4. Cálculo de Disonancia
            # CMC
            manifold = self.cmc.build(V_hat, self.graph, epsilon_used)

            # 5. DQE
            D_s = self.dqe.compute_dissonance(
                audit_input, V_hat, self.graph, context_input=context_input
            )

            admitted = False
            correction_flag = False
            y_corrected = audit_input
            y_corrected_for_metrics = audit_input
            D_f = 0.0

            # Allow a small slack for near-boundary compliance to avoid noisy corrections
            tolerance_slack = max(1e-6, min(0.01, epsilon_used * 0.1))
            if D_s <= epsilon_used + tolerance_slack:
                admitted = True
                y_corrected = audit_input
                correction_flag = False
                y_corrected_for_metrics = audit_input
            else:
                # En la arquitectura no se realiza corrección ex-post (SPSA / proyección)
                admitted = False
                correction_flag = False
                y_corrected = audit_input
                y_corrected_for_metrics = audit_input

            # Convertir ndarrays a listas de forma segura para toda la orquestación
            if isinstance(y_corrected, np.ndarray):
                y_corrected = y_corrected.tolist()
            elif hasattr(y_corrected, "distribution") and isinstance(
                y_corrected.distribution, np.ndarray
            ):
                # Preserve SemanticPayload-like structures when they contain readable text.
                if not (
                    hasattr(y_corrected, "source_text") and hasattr(y_corrected, "text_content")
                ):
                    y_corrected = y_corrected.distribution.tolist()

            y_corrected_for_metrics = audit_input if admitted else y_corrected_for_metrics

            # 5. Evaluate logical and context dissonance
            from idicoc_notary_core.audit.graph.property_graph_evaluator import (
                PropertyGraphEvaluator,
            )

            evaluator = PropertyGraphEvaluator(self.graph)
            d_logic = evaluator.evaluate(y_corrected_for_metrics)

            d_context = 0.0
            contradictory_contexts = []
            if context_input and hasattr(
                self.dissonance_strategy, "_compute_context_contradiction"
            ):
                d_context, contradictory_contexts = (
                    self.dissonance_strategy._compute_context_contradiction(
                        y_corrected_for_metrics, context_input
                    )
                )

            # Compute violated policies
            violated_list = []
            try:
                violated_nodes = evaluator.get_violated_policies(y_corrected_for_metrics)
                for vn in violated_nodes:
                    violated_list.append(f"{vn['id']}: {vn['text']} ({vn['hardness'].upper()})")
            except Exception as ex:
                self.logger.warning(f"Error computing violated policies: {ex}")

            if d_context > 0.4:
                for ctx_text in contradictory_contexts:
                    violated_list.append(f"Contradicción RAG: {ctx_text} (SOFT)")

            # 6. AEM (Hebra segura mediante Lock de exclusión mutua)
            aem_record = {
                "d_s": D_s,
                "d_f": D_f,
                "epsilon": epsilon_used,
                "correction_flag": correction_flag,
                "violated_policies": violated_list,
                "user_input": user_input,
                "audit_input": (
                    str(audit_input) if isinstance(audit_input, np.ndarray) else audit_input
                ),
                "timestamp": timestamp,
            }
            with self._aem_lock:
                if admitted:
                    self.aem.record_admission(aem_record)
                else:
                    self.aem.record_rejection(aem_record)

                total_sigs, valid_sigs, rej_sigs = self.aem.get_counters()

            # 7. CTM
            v_hat_payload = getattr(V_hat, "measure_vector", getattr(V_hat, "data", V_hat))
            if isinstance(v_hat_payload, np.ndarray):
                v_hat_payload = v_hat_payload.tolist()
            invariant_hash = sha256_hex(canonical_json(v_hat_payload))
            graph_hash = sha256_hex(canonical_json(self.graph.nodes))

            from idicoc_notary_core.utils.data_converter import DataConverter

            normalize_payload = DataConverter.normalize_payload

            payload_data = normalize_payload(y_corrected)
            if (
                isinstance(payload_data, list)
                and hasattr(audit_input, "source_text")
                and hasattr(audit_input, "distribution")
                and hasattr(audit_input, "text_content")
            ):
                payload_data = {
                    "payload_type": getattr(audit_input, "payload_type", None),
                    "source_text": getattr(audit_input, "source_text", None),
                    "text_content": getattr(audit_input, "text_content", None),
                    "distribution": payload_data,
                }

            structural_repr = normalize_payload(audit_input if not correction_flag else y_corrected)

            metadata = {
                "timestamp": timestamp,
                "d_s": D_s,
                "d_f": D_f,
                "epsilon_used": epsilon_used,
                "epsilon": epsilon_used,
                "correction_flag": correction_flag,
                "admission_metrics": {
                    "admitted": admitted,
                    "structural": structural_repr,
                },
                "audit_metrics": {"d_s": D_s, "d_logic": d_logic},
                "admission_breach": not admitted,
                "violated_policies": violated_list,
                "instance_name": self.config.instance_name,
                "client_id": client_id or self.config.client_id,
                "trace_input": trace_input or self.config.trace_input,
                "invariant_state_hash": invariant_hash,
                "property_graph_hash": graph_hash,
                "user_input": user_input or "",
                "context_input": context_input or [],
                "hardware_contained": True,
                "aem_counters": {
                    "total_signals": total_sigs,
                    "valid_signals": valid_sigs,
                    "rejected_signals": rej_sigs,
                },
                "algebraic_components": {
                    "d_0": 0.0,
                    "d_1": getattr(self.dissonance_strategy, "_d_inv_from_pair", lambda a, b: 0.0)(
                        y_corrected_for_metrics, V_hat
                    ),
                    "d_2": d_logic,
                    "d_3": evaluator.compute_temporal(y_corrected_for_metrics),
                    "d_4": 0.0,
                    "d_5": 0.0,
                    "d_6": 0.0,
                },
                "d_context": d_context,
                "contradictory_contexts": contradictory_contexts,
                "S_i": (1.0 - D_s) * epsilon_used,
            }
            metadata.update(self.config.extra_metadata)

            canonical_state = CanonicalStateDTO(
                data=payload_data,
                metadata=metadata,
                source_policies=all_policies,
            )

            kernel_result: dict[str, Any] = {"status": "uncommitted"}
            receipt = {"status": "uncommitted"}

            if self.config.ctm_mode == "full":
                # Generar ID de transacción único
                tx_id = f"tx_{invariant_hash}_{int(datetime.now(timezone.utc).timestamp())}"

                # Payload de seguridad del WAL
                wal_payload = {
                    "canonical_state": payload_data,
                    "dissonance": D_s,
                    "invariant_state_hash": invariant_hash,
                    "property_graph_hash": graph_hash,
                    "timestamp": timestamp,
                    "admitted": admitted,
                    "violated_policies": violated_list,
                    "user_input": user_input or "",
                }

                # Escribir al WAL local antes de interactuar con DB/Red síncrona
                self.wal.write(tx_id, wal_payload)

                try:
                    self.ctm.commit(
                        canonical_state=payload_data,
                        dissonance=D_s,
                        epsilon=epsilon_used,
                        property_graph=self.graph,
                        timestamp=timestamp,
                        invariant_state_hash=invariant_hash,
                        property_graph_hash=graph_hash,
                        aem_counters={
                            "total_signals": total_sigs,
                            "valid_signals": valid_sigs,
                            "rejected_signals": rej_sigs,
                        },
                    )
                    kernel_result = {
                        "status": "committed",
                        "root_hash": self.ctm.root_hash,
                    }
                    if self.kernel_client:
                        receipt = self.kernel_client.commit(
                            canonical_state=payload_data,
                            dissonance=D_s,
                            fact_dissonance=0.0,
                            epsilon=epsilon_used,
                            correction_flag=correction_flag,
                            source=self.config.instance_name,
                            metadata=metadata,
                        )
                    else:
                        receipt = kernel_result

                    # Sellar confirmación de éxito en el WAL local
                    self.wal.mark_completed(tx_id)

                except Exception as exc:
                    self.logger.error("CTM commit failed", exc_info=exc)
                    kernel_result = {"status": "uncommitted", "error": str(exc)}
                    receipt = {"status": "uncommitted", "error": str(exc)}
            elif self.config.ctm_mode == "log_only":
                kernel_result = {"status": "log_only"}
                receipt = {"status": "log_only"}
            else:
                kernel_result = {"status": "disabled"}
                receipt = {"status": "disabled"}

            if added_dynamic_ids:
                for ax_id in added_dynamic_ids:
                    self.graph.nodes.pop(ax_id, None)
                self.graph.detect_conflicts()

            return {
                "canonical_state": canonical_state,
                "output": y_corrected if admitted else audit_input,
                "kernel_result": kernel_result,
                "audit_receipt": receipt,
                "context_chunks": context_chunks,
            }

        except Exception as exc:
            if added_dynamic_ids:
                for ax_id in added_dynamic_ids:
                    self.graph.nodes.pop(ax_id, None)
                self.graph.detect_conflicts()
            return self._build_fallback_result(
                "failed",
                str(exc),
                epsilon_used,
                trace_input,
                client_id,
                context_policies,
                context_input,
            )

    def _build_fallback_result(
        self,
        status: str,
        reason: str,
        epsilon_used: float,
        trace_input: str,
        client_id: str | None,
        context_policies: Optional[List[str | Dict[str, Any]]],
        context_input: Optional[List[str]],
    ) -> Dict[str, Any]:
        """Genera una respuesta segura de fallback en caso de error crónico o entrada inválida."""
        timestamp = datetime.now(timezone.utc).isoformat()
        fallback_metadata = {
            "timestamp": timestamp,
            "d_s": 1.0,
            "d_f": 1.0,
            "epsilon_used": epsilon_used,
            "epsilon": epsilon_used,
            "correction_flag": False,
            "admission_metrics": {"admitted": False, "error": reason},
            "audit_metrics": {"error": reason},
            "admission_breach": True,
            "instance_name": self.config.instance_name,
            "client_id": client_id or self.config.client_id,
            "trace_input": trace_input or self.config.trace_input,
            "invariant_state_hash": "",
            "property_graph_hash": "",
            "algebraic_components": {
                "d_0": 0.0,
                "d_1": 0.0,
                "d_2": 1.0,
                "d_3": 0.0,
                "d_4": 0.0,
                "d_5": 0.0,
                "d_6": 0.0,
            },
        }
        fallback_metadata.update(self.config.extra_metadata)
        fallback_state = CanonicalStateDTO(
            data=f"[ERROR] {reason}",
            metadata=fallback_metadata,
            source_policies=context_policies or [],
        )
        return {
            "canonical_state": fallback_state,
            "output": f"[ERROR] {reason}",
            "kernel_result": {"status": status, "error": reason},
            "audit_receipt": {"status": "uncommitted", "error": reason},
            "context_chunks": context_input or [],
        }

    def reconcile_wal(self) -> int:
        """
        Intenta reconciliar (re-commit) las transacciones pendientes en el WAL local.
        """
        pending_txs = self.wal.recover_pending_transactions()
        if not pending_txs:
            return 0

        success_count = 0
        for tx_id, payload in pending_txs.items():
            try:
                canonical_state = payload.get("canonical_state")
                dissonance = payload.get("dissonance", 0.0)
                invariant_state_hash = payload.get("invariant_state_hash", "")
                property_graph_hash = payload.get("property_graph_hash", "")
                timestamp = payload.get("timestamp", datetime.now(timezone.utc).isoformat())

                self.ctm.commit(
                    canonical_state=canonical_state,
                    dissonance=dissonance,
                    epsilon=self.config.rigidity_epsilon,
                    property_graph=self.graph,
                    timestamp=timestamp,
                    invariant_state_hash=invariant_state_hash,
                    property_graph_hash=property_graph_hash,
                    aem_counters={
                        "total_signals": 1,
                        "valid_signals": 1,
                        "rejected_signals": 0,
                    },
                )

                self.wal.mark_completed(tx_id)
                success_count += 1
                self.logger.info(f"Transacción {tx_id} reconciliada y confirmada con éxito.")
            except Exception as e:
                self.logger.error(f"Fallo al reconciliar la transacción {tx_id}: {e}")

        return success_count

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import threading
from idicoc_notary_core.kernel.custody.merkle_dag import (
    CustodialTraceManager,
    EnvHardwareSealer,
    MerkleDAG,
)
from idicoc_notary_core.kernel.deviation.dqe import DissonanceCalculator
from idicoc_notary_core.kernel.dse.dse import AxiomExtractor
from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph
from idicoc_notary_core.kernel.manifold.cmc import ManifoldConstructor
from idicoc_notary_core.kernel.pipeline.kernel import CustodialKernel
from idicoc_notary_core.kernel.projection.invariant_state_generator import InvariantStateGenerator
from idicoc_notary_core.kernel.source.anchor import SourceAnchor
from idicoc_notary_core.kernel.verification.registry import ProjectionRegistry
from idicoc_notary_core.kernel.verification.verifier import InvariantVerifier
from idicoc_notary_core.utils.hashing import canonical_json, sha256_hex
from idicoc_notary_core.utils.logger import get_logger

from .base import CanonicalStateDTO
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
    ) -> None:
        self.config = config
        self.graph_cache = graph_cache
        self.graph = PropertyGraph(embedding_signature=self.config.embedding_signature)
        self.logger = get_logger("audit_flow.pipeline")
        self.aem = AuditEntropyModule()
        self._aem_lock = threading.Lock()

        self.anchor = SourceAnchor(np.zeros(1, dtype=float))

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
            elif backend_type_lower == "postgres":
                from .persistence.postgres_backend import PostgresCTMStorage
                uri = getattr(self.config, "ctm_postgres_uri", None)
                kwargs = getattr(self.config, "ctm_storage_kwargs", {})
                ctm_storage = PostgresCTMStorage(connection_uri=uri, **kwargs)
            elif backend_type_lower == "dynamodb":
                from .persistence.dynamodb_backend import DynamoDBStorage
                table = getattr(self.config, "ctm_dynamodb_table", None)
                kwargs = getattr(self.config, "ctm_storage_kwargs", {})
                ctm_storage = DynamoDBStorage(table_name=table, **kwargs)
            elif backend_type_lower == "qldb":
                from .persistence.qldb_backend import QLDBCTMStorage
                ledger = getattr(self.config, "ctm_qldb_ledger", None)
                kwargs = getattr(self.config, "ctm_storage_kwargs", {})
                ctm_storage = QLDBCTMStorage(ledger_name=ledger, **kwargs)
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
            anchor=self.anchor,
            registry=self.registry,
            delta_fp=self.config.isg_delta_fp,
            config=self.config,
        )
        self.verifier = InvariantVerifier(self.anchor)
        self.dse = AxiomExtractor(self.graph, self.config)
        self.dissonance_strategy = self._create_dissonance_strategy()
        self.dqe = DissonanceCalculator(
            strategy=self.dissonance_strategy,
            delta_fp=self.config.isg_delta_fp,
        )
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
            "delta_fp": self.config.isg_delta_fp,
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
            KernelCustodyClient(ctm=self.ctm)
            if self.config.ctm_mode == "full"
            else None
        )
        
        # Inicializar Write-Ahead Logger para resiliencia Enterprise
        import os
        wal_path = getattr(self.config, "ctm_wal_path", None)
        if not wal_path:
            wal_path = os.path.join(os.path.dirname(self.config.ctm_nodes_path or "."), "ctm_wal.log")
        from .persistence.ctm_wal import WriteAheadLogger
        self.wal = WriteAheadLogger(wal_path)
        
        # Recuperación automática al arranque
        pending_txs = self.wal.recover_pending_transactions()
        if pending_txs:
            self.logger.warning(
                f"Se detectaron {len(pending_txs)} transacciones pendientes de confirmación en el WAL local. "
                "Requiere reconciliación manual o resincronización automatizada."
            )

        self._initialized = False
        self.initialize()

    def _create_dissonance_strategy(self) -> DissonanceStrategyProtocol:
        return self.config.dissonance_strategy(config=self.config)

    def initialize(self) -> None:
        self._load_initial_axioms()
        self._initialized = True

    def _load_initial_axioms(self) -> None:
        """Carga y procesa axiomas estáticos, usando caché si está disponible."""
        if not self.config.axiom_loader:
            return

        # 1. Intentar recuperar desde caché
        tenant_id = self.config.client_id
        axioms_data = self.config.axiom_loader.load_axioms()
        
        # Calcular hash canónico de los datos
        content_hash = sha256_hex(canonical_json(axioms_data))
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

        for idx, axiom_dict in enumerate(axioms_data):
            axiom_id = axiom_dict.get("axiom_id") or axiom_dict.get("id") or f"axiom_loaded_{idx}"
            
            # Precomputar embedding
            if "embedding" not in axiom_dict:
                text_to_embed = axiom_dict.get("text") or axiom_dict.get("description") or str(axiom_dict)
                try:
                    vec = embed_service.encode(
                        text_to_embed, 
                        model_name=self.config.semantic_embedding_model, 
                        normalize_embeddings=self.config.embedding_normalize
                    )
                    axiom_dict["embedding"] = vec.tolist()
                except Exception as e:
                    self.logger.warning(f"No se pudo precomputar embedding para {axiom_id}: {e}")

            self.graph.add_axiom(axiom_id, axiom_dict)
            
        self.graph.detect_conflicts()
        self.logger.info(f"Loaded {len(axioms_data)} static axioms into the PropertyGraph.")

        # 3. Guardar en caché si está habilitada
        if self.graph_cache:
            self.graph_cache.set(cache_key, self.graph)
            self.logger.info("PropertyGraph guardado en caché.")

    def execute(
        self,
        audit_input: Any,
        context_input: Optional[List[str]] = None,
        context_axioms: Optional[List[str]] = None,
        epsilon_override: float | None = None,
        trace_input: str = "",
        client_id: str | None = None,
    ) -> Dict[str, Any]:
        epsilon_used = epsilon_override if epsilon_override is not None else self.config.rigidity_epsilon
        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Validación de entrada mínima
        if audit_input is None or (isinstance(audit_input, str) and not audit_input.strip()):
            return self._build_fallback_result(
                "empty_input", "Entrada vacía o nula", epsilon_used, trace_input, client_id, context_axioms, context_input
            )

        try:
            context_chunks = context_input or []
            all_axioms = list(context_axioms) if context_axioms else []

            # 2. ISG
            V_hat = self.isg.generate(audit_input)

            # 3. DSE (Solo lectura)
            # El PropertyGraph es inmutable en tiempo de ejecución.
            # Los axiomas fijos ya se cargaron. El contexto dinámico se pasará
            # a la estrategia para su evaluación temporal pero no se guardará en el grafo.

            # 4. Cálculo de Disonancia
            # CMC
            manifold = self.cmc.build(V_hat, self.graph, epsilon_used)

            # 5. DQE
            D_s = self.dqe.compute_dissonance(audit_input, V_hat, self.graph)

            admitted = False
            correction_flag = False
            y_corrected = audit_input
            D_f = 0.0

            if D_s <= epsilon_used:
                admitted = True
                y_corrected = audit_input
                correction_flag = False
            else:
                y_corrected = self.dqe.project_to_manifold(audit_input, manifold, V_hat, self.graph)
                D_s_corrected = self.dqe.compute_dissonance(y_corrected, V_hat, self.graph)
                if D_s_corrected <= epsilon_used:
                    admitted = True
                    correction_flag = True
                else:
                    admitted = False
                    correction_flag = False

            # Convertir ndarrays a listas de forma segura para toda la orquestación
            if isinstance(y_corrected, np.ndarray):
                y_corrected = y_corrected.tolist()
            elif hasattr(y_corrected, "distribution") and isinstance(y_corrected.distribution, np.ndarray):
                y_corrected = y_corrected.distribution.tolist()

            # 6. AEM (Hebra segura mediante Lock de exclusión mutua)
            aem_record = {
                "d_s": D_s,
                "d_f": D_f,
                "epsilon": epsilon_used,
                "correction_flag": correction_flag,
                "violated_axioms": [],
                "audit_input": str(audit_input) if isinstance(audit_input, np.ndarray) else audit_input,
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

            from idicoc_notary_core.audit.graph.property_graph_evaluator import PropertyGraphEvaluator
            evaluator = PropertyGraphEvaluator(self.graph)
            d_logic = evaluator.evaluate(y_corrected)

            metadata = {
                "timestamp": timestamp,
                "d_s": D_s,
                "d_f": D_f,
                "epsilon_used": epsilon_used,
                "epsilon": epsilon_used,
                "delta_fp": self.config.isg_delta_fp,
                "correction_flag": correction_flag,
                "admission_metrics": {
                    "admitted": admitted,
                    "structural": str(audit_input) if not correction_flag else y_corrected,
                },
                "audit_metrics": {"d_s": D_s, "d_logic": d_logic},
                "admission_breach": not admitted,
                "instance_name": self.config.instance_name,
                "client_id": client_id or self.config.client_id,
                "trace_input": trace_input or self.config.trace_input,
                "invariant_state_hash": invariant_hash,
                "property_graph_hash": graph_hash,
                "aem_counters": {
                    "total_signals": total_sigs,
                    "valid_signals": valid_sigs,
                    "rejected_signals": rej_sigs,
                },
                "algebraic_components": {
                    "d_0": 0.0,
                    "d_1": getattr(self.dissonance_strategy, "_d_inv_from_pair", lambda a, b: 0.0)(y_corrected, V_hat),
                    "d_2": d_logic,
                    "d_3": evaluator.compute_temporal(y_corrected),
                    "d_4": 0.0,
                    "d_5": 0.0,
                    "d_6": 0.0,
                }
            }
            metadata.update(self.config.extra_metadata)
            
            payload_data = y_corrected if admitted else "[REJECTED]"

            canonical_state = CanonicalStateDTO(
                data=payload_data,
                metadata=metadata,
                source_axioms=all_axioms,
            )

            kernel_result: dict[str, Any] = {"status": "uncommitted"}
            receipt = {"status": "uncommitted"}

            if self.config.ctm_mode == "full":
                # Generar ID de transacción único
                tx_id = f"tx_{invariant_hash}_{int(datetime.now(timezone.utc).timestamp())}"
                
                # Payload de seguridad del WAL
                wal_payload = {
                    "canonical_state": y_corrected,
                    "dissonance": D_s,
                    "invariant_state_hash": invariant_hash,
                    "property_graph_hash": graph_hash,
                    "timestamp": timestamp
                }
                
                # Escribir al WAL local antes de interactuar con DB/Red síncrona
                self.wal.write(tx_id, wal_payload)

                try:
                    self.ctm.commit(
                        canonical_state=y_corrected,
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
                            canonical_state=y_corrected,
                            dissonance=D_s,
                            fact_dissonance=0.0,
                            epsilon=epsilon_used,
                            delta_fp=self.config.isg_delta_fp,
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

            return {
                "canonical_state": canonical_state,
                "output": y_corrected if admitted else audit_input,
                "kernel_result": kernel_result,
                "audit_receipt": receipt,
                "context_chunks": context_chunks,
            }

        except Exception as exc:
            return self._build_fallback_result("failed", str(exc), epsilon_used, trace_input, client_id, context_axioms, context_input)

    def _build_fallback_result(
        self, status: str, reason: str, epsilon_used: float, trace_input: str, client_id: str | None, context_axioms: Optional[List[str]], context_input: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Genera una respuesta segura de fallback en caso de error crónico o entrada inválida."""
        timestamp = datetime.now(timezone.utc).isoformat()
        fallback_metadata = {
            "timestamp": timestamp,
            "d_s": 1.0,
            "d_f": 1.0,
            "epsilon_used": epsilon_used,
            "epsilon": epsilon_used,
            "delta_fp": self.config.isg_delta_fp,
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
            source_axioms=context_axioms or [],
        )
        return {
            "canonical_state": fallback_state,
            "output": f"[ERROR] {reason}",
            "kernel_result": {"status": status, "error": reason},
            "audit_receipt": {"status": "uncommitted", "error": reason},
            "context_chunks": context_input or [],
        }

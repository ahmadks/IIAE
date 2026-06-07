"""
CTM Orchestration Module - Manages Custodial Trace Manager and Write-Ahead Logger.
"""

import os
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from idicoc_core.api.schemas import SessionContext
from idicoc_core.ctm.merkle_dag import (
    CustodialTraceManager,
    MerkleDAG,
    EnvHardwareSealer,
    FileCTMStorage,
)
from idicoc_core.ctm.wal_logger import WriteAheadLogger
from idicoc_core.utils.logger import get_logger

logger = get_logger("pipeline.ctm_orchestration")


class CTMOrchestrator:
    """Manages CTM (Custodial Trace Manager) and WAL (Write-Ahead Logger)."""

    def __init__(self, config: Any) -> None:
        self.config = config

        # Initialize CTM (Custodial Trace Manager)
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
        self._reconcile_wal()

    def _reconcile_wal(self) -> None:
        """Recover and reconcile pending WAL transactions."""
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

    def commit_audit_trace(
        self,
        user_prompt: str,
        rag_context: str,
        llm_output: str,
        session_context: SessionContext,
        d_s: float,
        is_admitted: bool,
        violations: List[str],
        raw_metrics: Dict[str, Any],
    ) -> None:
        """
        Commit audit trace to CTM and WAL.
        """
        if self.config.ctm_mode != "full":
            logger.info("[CTM] Mode: %s (skipped)", self.config.ctm_mode)
            return

        import time

        t_ctm_start = time.perf_counter()
        try:
            tx_id = f"tx_{hash(llm_output)}_{int(datetime.now(timezone.utc).timestamp())}"
            timestamp = datetime.now(timezone.utc).isoformat()

            # Prepare WAL payload
            wal_payload = {
                "user_prompt": user_prompt,
                "rag_context": rag_context,
                "output": llm_output,
                "dissonance": d_s,
                "is_admitted": is_admitted,
                "violations": violations,
                "timestamp": timestamp,
            }

            # Extract distribution from context
            dist_val = self._extract_distribution(session_context, llm_output)
            if dist_val is not None:
                if hasattr(dist_val, "tolist"):
                    dist_val = dist_val.tolist()
                wal_payload["distribution"] = dist_val

            # Build dissonance components
            dissonance_components = {
                "d_axiomatic": float(raw_metrics.get("d_logic", d_s)),
                "d_context": float(raw_metrics.get("d_context", 0.0)),
            }
            wal_payload["dissonance_components"] = dissonance_components

            # Write to WAL first
            self.wal.write(tx_id, wal_payload)

            # Commit to CTM
            try:
                self.ctm.commit_trace(
                    session_context,
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

            t_ctm_elapsed = time.perf_counter() - t_ctm_start
            logger.info("[TIMING] CTM commit: %.3f sec", t_ctm_elapsed)

        except Exception as exc:
            logger.error(f"Error during CTM orchestration: {exc}", exc_info=True)

    @staticmethod
    def _extract_distribution(session_context: SessionContext, llm_output: str) -> Any:
        """Extract distribution from session context or parse from LLM output."""
        dist_val = None

        # Try to get from context
        if isinstance(session_context, dict):
            dist_val = session_context.get("distribution") or session_context.get(
                "metadata", {}
            ).get("distribution")
        else:
            dist_val = getattr(session_context, "distribution", None) or (
                getattr(session_context, "metadata", None) or {}
            ).get("distribution")

        # Try to parse from LLM output if not found
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

        return dist_val

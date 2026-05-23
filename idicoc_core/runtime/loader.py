# idicoc_core/runtime/loader.py
from __future__ import annotations
from typing import Any, Dict

from idicoc_core.core.custody.merkle_dag import CustodialTraceManager


def recover_input_from_snapshot(root_hash: str, ctm: CustodialTraceManager) -> Any:
    """
    Reconstruye el input previo a la divergencia a partir del último nodo FAILURE.

    Este módulo es deliberadamente minimalista:
    - No interpreta semántica del snapshot.
    - No reescribe historia.
    - No altera el DAG.
    - Solo extrae lo que el Kernel dejó sellado.

    El snapshot debe contener:
        snapshot = {
            "kernel_state": {...},
            "breach": {...}
        }

    Y dentro de kernel_state:
        kernel_state["buffers"][0] = admitted_input_original
    """

    failure_snapshot = ctm.get_last_failure_snapshot(root_hash)
    kernel_state = failure_snapshot.get("kernel_state")

    if not kernel_state:
        raise RuntimeError("Snapshot inválido: falta 'kernel_state'.")

    # Recuperación del Buffer 0 (donde reside el admitted_input original)
    buffers = kernel_state.get("buffers")
    if not isinstance(buffers, list) or len(buffers) < 1:
        raise RuntimeError("Snapshot inválido: buffers ausentes o malformados.")

    recovered_input = buffers[0]
    
    if recovered_input is None:
        raise RuntimeError("Buffer 0 vacío: el Kernel falló antes de completar la admisión.")

    return recovered_input
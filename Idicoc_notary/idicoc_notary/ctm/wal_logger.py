from __future__ import annotations
import os
import json
import hashlib
import threading
from typing import Any, Dict
from idicoc_notary.utils.logger import get_logger

class WriteAheadLogger:
    """
    WAL (Write-Ahead Logger) de nivel de misión crítica.
    Asegura la atomicidad y durabilidad de las transacciones del Notario localmente 
    en disco antes de realizar commits hacia motores de almacenamiento distribuidos.
    Incorpora checksums criptográficos SHA-256 en cada entrada para proteger la 
    integridad física de los logs contra bit-flips o escrituras truncadas.
    """

    def __init__(self, wal_path: str) -> None:
        self.wal_path = wal_path
        self.logger = get_logger("audit_flow.wal")
        self._lock = threading.Lock()
        
        parent_dir = os.path.dirname(self.wal_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

    def _calculate_checksum(self, transaction_id: str, payload: Dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        target = f"{transaction_id}:{serialized}".encode("utf-8")
        return hashlib.sha256(target).hexdigest()

    def write(self, transaction_id: str, payload: Dict[str, Any]) -> bool:
        checksum = self._calculate_checksum(transaction_id, payload)
        entry = {
            "transaction_id": transaction_id,
            "status": "PENDING",
            "checksum": checksum,
            "payload": payload
        }
        
        with self._lock:
            try:
                with open(self.wal_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
                return True
            except Exception as e:
                self.logger.error(f"Fallo crítico al escribir al Write-Ahead Log (WAL): {e}", exc_info=e)
                return False

    def mark_completed(self, transaction_id: str) -> None:
        entry = {
            "transaction_id": transaction_id,
            "status": "COMPLETED"
        }
        with self._lock:
            try:
                with open(self.wal_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
            except Exception as e:
                self.logger.error(f"Fallo al marcar confirmación en WAL para {transaction_id}: {e}")

    def recover_pending_transactions(self) -> Dict[str, Any]:
        if not os.path.exists(self.wal_path):
            return {}

        pending_map: Dict[str, Dict[str, Any]] = {}
        
        with self._lock:
            try:
                with open(self.wal_path, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            tx_id = entry.get("transaction_id")
                            status = entry.get("status")
                            
                            if status == "PENDING":
                                payload = entry.get("payload")
                                stored_checksum = entry.get("checksum")
                                
                                if payload is None or stored_checksum is None:
                                    self.logger.critical(
                                        f"WAL CORRUPTO [Línea {line_num}]: Entrada PENDING sin payload o checksum. Abortando recuperación."
                                    )
                                    return {}
                                
                                calculated_checksum = self._calculate_checksum(tx_id, payload)
                                if calculated_checksum != stored_checksum:
                                    self.logger.critical(
                                        f"FALLO DE INTEGRIDAD CRÍTICO [Línea {line_num}]: "
                                        f"El checksum del WAL ({stored_checksum}) no coincide con el calculado ({calculated_checksum}). "
                                        "Posible corrupción física o truncado incompleto de disco. Abortando recuperación."
                                    )
                                    return {}
                                
                                pending_map[tx_id] = payload
                            elif status == "COMPLETED":
                                if tx_id in pending_map:
                                    del pending_map[tx_id]
                        except json.JSONDecodeError:
                            self.logger.critical(
                                f"WAL CORRUPTO [Línea {line_num}]: JSON inválido (escritura parcial). Abortando recuperación."
                            )
                            return {}
            except Exception as e:
                self.logger.error(f"Error al analizar el registro WAL durante la recuperación: {e}")
                return {}

        return pending_map

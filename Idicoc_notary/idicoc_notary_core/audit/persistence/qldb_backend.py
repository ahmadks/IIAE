from __future__ import annotations

import json
from typing import Any, Dict, Optional
from .backend import CTMStorageBackend
from idicoc_notary_core.audit.exceptions import PersistenceError
from idicoc_notary_core.utils.logger import get_logger


class QLDBCTMStorage(CTMStorageBackend):
    """Backend de almacenamiento CTM usando Amazon QLDB.

    Aprovecha el ledger transaccional inmutable para guardar las evidencias del Merkle DAG.

    ===========================================================================
    EXPLICACIÓN EN LENGUAJE LLANO (PARA EL INGENIERO DE CONTROL A LAS 3:00 AM):
    Este componente guarda las pruebas del Merkle DAG en un libro contable inmutable de Amazon QLDB.
    En producción (`mock=False`), requiere obligatoriamente que configures un ledger activo.
    Cualquier error de comunicación con el ledger arrojará un PersistenceError inmediatamente.
    Usa `mock=True` para pruebas locales rápidas e independientes de AWS.
    ===========================================================================
    """
    def __init__(
        self,
        ledger_name: Optional[str] = None,
        mock: bool = False,
        region_name: str = "us-east-1",
        **kwargs: Any
    ):
        self.mock = mock or kwargs.get("mock", False)
        self.ledger_name = ledger_name
        self.region_name = region_name
        self.kwargs = {k: v for k, v in kwargs.items() if k != "mock"}
        self.logger = get_logger("persistence.qldb")

        self._mock_nodes: Dict[str, Dict[str, Any]] = {}
        self._mock_root: Optional[str] = None

        if self.mock:
            self.logger.warning(
                "WARNING: QLDBCTMStorage está operando en MODO MOCK. "
                "Este modo NO es seguro para entornos de producción y solo debe "
                "usarse en pruebas o desarrollo local."
            )
        else:
            if not self.ledger_name:
                raise ValueError(
                    "QLDBCTMStorage requiere 'ledger_name' cuando no opera en modo mock."
                )
            
            try:
                import importlib
                qldb_driver = importlib.import_module("pyqldb.driver.qldb_driver")
                QldbDriver = qldb_driver.QldbDriver
                self._driver = QldbDriver(
                    ledger_name=self.ledger_name,
                    region_name=self.region_name,
                    **self.kwargs
                )
                self._setup_ledger()
            except ImportError as exc:
                raise RuntimeError(
                    "No se pudo importar pyqldb para producción. Asegúrate de instalarlo."
                ) from exc

    def _setup_ledger(self) -> None:
        try:
            def create_tables(txn: Any) -> None:
                txn.execute_statement("CREATE TABLE CTMNodes")
                txn.execute_statement("CREATE INDEX ON CTMNodes (node_hash)")
                txn.execute_statement("CREATE TABLE CTMRoots")
            self._driver.execute_lambda(create_tables)
        except Exception as exc:
            if "already exists" not in str(exc).lower():
                raise PersistenceError(f"Fallo al inicializar tablas en QLDB: {exc}") from exc

    def save_node(self, node_hash: str, node_data: Dict[str, Any]) -> None:
        if self.mock:
            self.logger.info(f"[QLDB MOCK] Guardando nodo {node_hash}")
            self._mock_nodes[node_hash] = node_data
            return

        try:
            def insert_node(txn: Any) -> None:
                cursor = txn.execute_statement(
                    "SELECT node_hash FROM CTMNodes WHERE node_hash = ?",
                    node_hash
                )
                if not list(cursor):
                    txn.execute_statement(
                        "INSERT INTO CTMNodes VALUE ?",
                        {
                            "node_hash": node_hash,
                            "node_data": json.dumps(node_data)
                        }
                    )
            self._driver.execute_lambda(insert_node)
        except Exception as exc:
            raise PersistenceError(f"Error al guardar nodo en Amazon QLDB: {exc}") from exc

    def load_node(self, node_hash: str) -> Optional[Dict[str, Any]]:
        if self.mock:
            self.logger.info(f"[QLDB MOCK] Cargando nodo {node_hash}")
            return self._mock_nodes.get(node_hash)

        try:
            def query_node(txn: Any) -> Optional[Dict[str, Any]]:
                cursor = txn.execute_statement(
                    "SELECT node_data FROM CTMNodes WHERE node_hash = ?",
                    node_hash
                )
                for row in cursor:
                    return json.loads(row.get("node_data"))
                return None
            return self._driver.execute_lambda(query_node)
        except Exception as exc:
            raise PersistenceError(f"Error al cargar nodo de Amazon QLDB: {exc}") from exc

    def load_all_nodes(self) -> Dict[str, Dict[str, Any]]:
        if self.mock:
            return dict(self._mock_nodes)

        try:
            def query_all(txn: Any) -> Dict[str, Dict[str, Any]]:
                cursor = txn.execute_statement("SELECT * FROM CTMNodes")
                nodes: Dict[str, Dict[str, Any]] = {}
                for row in cursor:
                    h = row.get("node_hash")
                    data = row.get("node_data")
                    if h and data:
                        nodes[h] = json.loads(data)
                return nodes
            return self._driver.execute_lambda(query_all)
        except Exception as exc:
            raise PersistenceError(f"Error al cargar todos los nodos de Amazon QLDB: {exc}") from exc

    def save_root_hash(self, root_hash: str) -> None:
        if self.mock:
            self.logger.info(f"[QLDB MOCK] Guardando hash raíz {root_hash}")
            self._mock_root = root_hash
            return

        try:
            def insert_root(txn: Any) -> None:
                txn.execute_statement("DELETE FROM CTMRoots")
                txn.execute_statement(
                    "INSERT INTO CTMRoots VALUE ?",
                    {"id": 1, "root_hash": root_hash}
                )
            self._driver.execute_lambda(insert_root)
        except Exception as exc:
            raise PersistenceError(f"Error al guardar hash raíz en Amazon QLDB: {exc}") from exc

    def load_root_hash(self) -> Optional[str]:
        if self.mock:
            return self._mock_root

        try:
            def query_root(txn: Any) -> Optional[str]:
                cursor = txn.execute_statement("SELECT root_hash FROM CTMRoots")
                for row in cursor:
                    return row.get("root_hash")
                return None
            return self._driver.execute_lambda(query_root)
        except Exception as exc:
            raise PersistenceError(f"Error al cargar hash raíz de Amazon QLDB: {exc}") from exc

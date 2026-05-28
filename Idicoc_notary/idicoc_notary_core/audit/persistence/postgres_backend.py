from __future__ import annotations

import logging
import json
from typing import Any, Dict, Optional
from .backend import CTMStorageBackend
from idicoc_notary_core.audit.exceptions import PersistenceError
from idicoc_notary_core.utils.logger import get_logger


class PostgresCTMStorage(CTMStorageBackend):
    """Backend de almacenamiento CTM usando PostgreSQL en producción.

    Guarda los nodos y el hash raíz en tablas PostgreSQL con soporte nativo de
    tipo JSONB y estampas de tiempo automáticas.

    ===========================================================================
    EXPLICACIÓN EN LENGUAJE LLANO (PARA EL INGENIERO DE CONTROL A LAS 3:00 AM):
    Este componente guarda los bloques del Merkle DAG en una base de datos Postgres.
    En producción (`mock=False`), exige que le proveas una URI de conexión válida. 
    Cualquier error de red o base de datos detendrá el flujo y lanzará una excepción
    del tipo PersistenceError para alertar a los sistemas de monitoreo inmediatamente.
    Solo usa `mock=True` en modo de prueba/desarrollo local.
    ===========================================================================
    """
    def __init__(
        self,
        connection_uri: Optional[str] = None,
        mock: bool = False,
        table_name: str = "ctm_nodes",
        root_table_name: str = "ctm_roots",
        **kwargs: Any
    ):
        self.mock = mock or kwargs.get("mock", False)
        self.connection_uri = connection_uri
        self.table_name = table_name
        self.root_table_name = root_table_name
        self.kwargs = {k: v for k, v in kwargs.items() if k != "mock"}
        self.logger = get_logger("persistence.postgres")

        self._mock_nodes: Dict[str, Dict[str, Any]] = {}
        self._mock_root: Optional[str] = None

        if self.mock:
            self.logger.warning(
                "WARNING: PostgresCTMStorage está operando en MODO MOCK. "
                "Este modo NO es seguro para entornos de producción y solo debe "
                "usarse en pruebas o desarrollo local."
            )
        else:
            if not self.connection_uri:
                raise ValueError(
                    "PostgresCTMStorage requiere 'connection_uri' cuando no opera en modo mock."
                )
            
            try:
                import importlib
                psycopg2 = importlib.import_module("psycopg2")
                psycopg2_extras = importlib.import_module("psycopg2.extras")
                self._conn_module = psycopg2
                self._cursor_factory = psycopg2_extras.RealDictCursor
                self._setup_database()
            except ImportError as exc:
                raise RuntimeError(
                    "No se pudo importar psycopg2 para producción. Asegúrate de instalarlo."
                ) from exc

    def _setup_database(self) -> None:
        try:
            conn = self._conn_module.connect(self.connection_uri, **self.kwargs)
            with conn.cursor() as cur:
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        node_hash VARCHAR(64) PRIMARY KEY,
                        node_data JSONB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.root_table_name} (
                        id INT PRIMARY KEY,
                        root_hash VARCHAR(64) NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                # Crear índice explícito sobre node_hash para búsquedas eficientes
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_hash ON {self.table_name} (node_hash);")
            conn.commit()
            conn.close()
        except Exception as exc:
            self.logger.error(f"Fallo al conectar o configurar la base de datos PostgreSQL: {exc}")
            raise PersistenceError(f"Error de base de datos Postgres: {exc}") from exc

    def save_node(self, node_hash: str, node_data: Dict[str, Any]) -> None:
        if self.mock:
            self.logger.info(f"[Postgres MOCK] Guardando nodo {node_hash}")
            self._mock_nodes[node_hash] = node_data
            return

        try:
            conn = self._conn_module.connect(self.connection_uri, **self.kwargs)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.table_name} (node_hash, node_data)
                    VALUES (%s, %s)
                    ON CONFLICT (node_hash) DO UPDATE SET node_data = EXCLUDED.node_data;
                    """,
                    (node_hash, json.dumps(node_data)),
                )
            conn.commit()
            conn.close()
        except Exception as exc:
            raise PersistenceError(f"Error al guardar nodo en Postgres: {exc}") from exc

    def load_node(self, node_hash: str) -> Optional[Dict[str, Any]]:
        if self.mock:
            self.logger.info(f"[Postgres MOCK] Cargando nodo {node_hash}")
            return self._mock_nodes.get(node_hash)

        try:
            conn = self._conn_module.connect(self.connection_uri, **self.kwargs)
            with conn.cursor(cursor_factory=self._cursor_factory) as cur:
                cur.execute(
                    f"SELECT node_data FROM {self.table_name} WHERE node_hash = %s;",
                    (node_hash,),
                )
                row = cur.fetchone()
                if row:
                    data = row["node_data"]
                    return json.loads(data) if isinstance(data, str) else data
            conn.close()
            return None
        except Exception as exc:
            raise PersistenceError(f"Error al cargar nodo de Postgres: {exc}") from exc

    def load_all_nodes(self) -> Dict[str, Dict[str, Any]]:
        if self.mock:
            return dict(self._mock_nodes)

        try:
            conn = self._conn_module.connect(self.connection_uri, **self.kwargs)
            nodes: Dict[str, Dict[str, Any]] = {}
            with conn.cursor(cursor_factory=self._cursor_factory) as cur:
                cur.execute(f"SELECT node_hash, node_data FROM {self.table_name};")
                for row in cur.fetchall():
                    h = row["node_hash"]
                    data = row["node_data"]
                    nodes[h] = json.loads(data) if isinstance(data, str) else data
            conn.close()
            return nodes
        except Exception as exc:
            raise PersistenceError(f"Error al cargar todos los nodos de Postgres: {exc}") from exc

    def save_root_hash(self, root_hash: str) -> None:
        if self.mock:
            self.logger.info(f"[Postgres MOCK] Guardando hash raíz {root_hash}")
            self._mock_root = root_hash
            return

        try:
            conn = self._conn_module.connect(self.connection_uri, **self.kwargs)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.root_table_name} (id, root_hash, updated_at)
                    VALUES (1, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET root_hash = EXCLUDED.root_hash, updated_at = CURRENT_TIMESTAMP;
                    """,
                    (root_hash,),
                )
            conn.commit()
            conn.close()
        except Exception as exc:
            raise PersistenceError(f"Error al guardar hash raíz en Postgres: {exc}") from exc

    def load_root_hash(self) -> Optional[str]:
        if self.mock:
            return self._mock_root

        try:
            conn = self._conn_module.connect(self.connection_uri, **self.kwargs)
            root_hash = None
            with conn.cursor(cursor_factory=self._cursor_factory) as cur:
                cur.execute(f"SELECT root_hash FROM {self.root_table_name} WHERE id = 1;")
                row = cur.fetchone()
                if row:
                    root_hash = row["root_hash"]
            conn.close()
            return root_hash
        except Exception as exc:
            raise PersistenceError(f"Error al cargar hash raíz de Postgres: {exc}") from exc

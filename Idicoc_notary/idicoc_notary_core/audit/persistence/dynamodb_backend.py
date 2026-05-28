from __future__ import annotations

from typing import Any, Dict, Optional
from .backend import CTMStorageBackend
from idicoc_notary_core.audit.exceptions import PersistenceError
from idicoc_notary_core.utils.logger import get_logger


class DynamoDBStorage(CTMStorageBackend):
    """Backend de almacenamiento CTM usando AWS DynamoDB.

    Almacena los bloques utilizando un atributo nativo de mapa de datos.

    ===========================================================================

    Este componente interactúa con la base de datos NoSQL DynamoDB de AWS.
    En producción (`mock=False`), exige que le proveas un nombre de tabla válido.
    Cualquier error de conexión o credenciales de AWS detendrá el flujo y lanzará una
    excepción del tipo PersistenceError.
    Usa `mock=True` únicamente para pruebas locales en memoria.
    ===========================================================================
    """

    def __init__(
        self,
        table_name: Optional[str] = None,
        mock: bool = False,
        region_name: str = "us-east-1",
        **kwargs: Any,
    ):
        self.mock = mock or kwargs.get("mock", False)
        self.table_name = table_name
        self.region_name = region_name
        self.kwargs = {k: v for k, v in kwargs.items() if k != "mock"}
        self.logger = get_logger("persistence.dynamodb")

        self._mock_nodes: Dict[str, Dict[str, Any]] = {}
        self._mock_root: Optional[str] = None

        # Atributos de conexión: se inicializan en None y solo se populan en modo producción.
        self._boto3: Optional[Any] = None
        self._dynamodb: Optional[Any] = None
        self._table: Optional[Any] = None

        if self.mock:
            self.logger.warning(
                "WARNING: DynamoDBStorage está operando en MODO MOCK. "
                "Este modo NO es seguro para entornos de producción y solo debe "
                "usarse en pruebas o desarrollo local."
            )
        else:
            if not self.table_name:
                raise ValueError(
                    "DynamoDBStorage requiere 'table_name' cuando no opera en modo mock."
                )

            try:
                import importlib

                boto3 = importlib.import_module("boto3")
                self._boto3 = boto3
                self._dynamodb = boto3.resource(
                    "dynamodb", region_name=self.region_name, **self.kwargs
                )
                self._table = self._dynamodb.Table(self.table_name)
            except ImportError as exc:
                raise RuntimeError(
                    "No se pudo importar boto3 para producción. Asegúrate de instalarlo."
                ) from exc

    def save_node(self, node_hash: str, node_data: Dict[str, Any]) -> None:
        if self.mock:
            self.logger.info(f"[DynamoDB MOCK] Guardando nodo {node_hash}")
            self._mock_nodes[node_hash] = node_data
            return

        assert self._table is not None, "_table debe estar inicializado en modo producción"
        try:
            # node_data se guarda directamente como un mapa nativo en DynamoDB
            self._table.put_item(
                Item={"node_hash": node_hash, "node_data": node_data, "type": "NODE"}
            )
        except Exception as exc:
            raise PersistenceError(f"Error al guardar nodo en DynamoDB: {exc}") from exc

    def load_node(self, node_hash: str) -> Optional[Dict[str, Any]]:
        if self.mock:
            self.logger.info(f"[DynamoDB MOCK] Cargando nodo {node_hash}")
            return self._mock_nodes.get(node_hash)

        assert self._table is not None, "_table debe estar inicializado en modo producción"
        try:
            response = self._table.get_item(Key={"node_hash": node_hash})
            item = response.get("Item")
            if item and "node_data" in item:
                return item["node_data"]
            return None
        except Exception as exc:
            raise PersistenceError(f"Error al cargar nodo de DynamoDB: {exc}") from exc

    def load_all_nodes(self) -> Dict[str, Dict[str, Any]]:
        if self.mock:
            return dict(self._mock_nodes)

        assert self._table is not None, "_table debe estar inicializado en modo producción"
        try:
            nodes: Dict[str, Dict[str, Any]] = {}
            response = self._table.scan(FilterExpression="attribute_exists(node_data)")
            for item in response.get("Items", []):
                h = item["node_hash"]
                nodes[h] = item["node_data"]
            return nodes
        except Exception as exc:
            raise PersistenceError(f"Error al escanear todos los nodos de DynamoDB: {exc}") from exc

    def save_root_hash(self, root_hash: str) -> None:
        if self.mock:
            self.logger.info(f"[DynamoDB MOCK] Guardando hash raíz {root_hash}")
            self._mock_root = root_hash
            return

        assert self._table is not None, "_table debe estar inicializado en modo producción"
        try:
            self._table.put_item(
                Item={"node_hash": "__root_hash__", "value": root_hash, "type": "ROOT"}
            )
        except Exception as exc:
            raise PersistenceError(f"Error al guardar hash raíz en DynamoDB: {exc}") from exc

    def load_root_hash(self) -> Optional[str]:
        if self.mock:
            return self._mock_root

        assert self._table is not None, "_table debe estar inicializado en modo producción"
        try:
            response = self._table.get_item(Key={"node_hash": "__root_hash__"})
            item = response.get("Item")
            if item:
                return item.get("value")
            return None
        except Exception as exc:
            raise PersistenceError(f"Error al cargar hash raíz de DynamoDB: {exc}") from exc

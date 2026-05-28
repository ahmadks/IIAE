import pytest
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.persistence import (
    PostgresCTMStorage,
    DynamoDBStorage,
    QLDBCTMStorage,
)
from idicoc_notary_core.audit.pipeline import IDICOCPipeline
from idicoc_notary_core.audit.exceptions import PersistenceError

def test_production_backends_strict_parameter_checking():
    """Verify that backends raise ValueError if required parameters are missing in production mode."""
    # 1. Postgres: mock=False requires connection_uri
    with pytest.raises(ValueError, match="connection_uri"):
        PostgresCTMStorage(mock=False, connection_uri=None)

    # 2. DynamoDB: mock=False requires table_name
    with pytest.raises(ValueError, match="table_name"):
        DynamoDBStorage(mock=False, table_name=None)

    # 3. QLDB: mock=False requires ledger_name
    with pytest.raises(ValueError, match="ledger_name"):
        QLDBCTMStorage(mock=False, ledger_name=None)

def test_production_backends_error_propagation():
    """Verify that backends do not silently fallback to mock when database errors occur in production."""
    # If psycopg2 is not installed, it raises RuntimeError. If it is installed but connection fails, it raises PersistenceError.
    # Both behaviors are correct (they bubble up the exception rather than swallowing it).
    with pytest.raises((RuntimeError, PersistenceError)):
        PostgresCTMStorage(connection_uri="postgresql://non_existent_user:pass@localhost:5432/non_existent_db", mock=False)

def test_production_backends_mock_mode():
    """Test Postgres, DynamoDB, and QLDB backends in explicit mock mode with logs."""
    # 1. Postgres
    pg_storage = PostgresCTMStorage(mock=True)
    assert pg_storage.load_root_hash() is None
    pg_storage.save_node("n1", {"node_hash": "n1", "val": 10})
    pg_storage.save_root_hash("n1")
    assert pg_storage.load_root_hash() == "n1"
    pg_node = pg_storage.load_node("n1")
    assert pg_node is not None
    assert pg_node["val"] == 10
    assert "n1" in pg_storage.load_all_nodes()

    # 2. DynamoDB
    ddb_storage = DynamoDBStorage(mock=True)
    assert ddb_storage.load_root_hash() is None
    ddb_storage.save_node("n2", {"node_hash": "n2", "val": 20})
    ddb_storage.save_root_hash("n2")
    assert ddb_storage.load_root_hash() == "n2"
    ddb_node = ddb_storage.load_node("n2")
    assert ddb_node is not None
    assert ddb_node["val"] == 20
    assert "n2" in ddb_storage.load_all_nodes()

    # 3. QLDB
    qldb_storage = QLDBCTMStorage(mock=True)
    assert qldb_storage.load_root_hash() is None
    qldb_storage.save_node("n3", {"node_hash": "n3", "val": 30})
    qldb_storage.save_root_hash("n3")
    assert qldb_storage.load_root_hash() == "n3"
    qldb_node = qldb_storage.load_node("n3")
    assert qldb_node is not None
    assert qldb_node["val"] == 30
    assert "n3" in qldb_storage.load_all_nodes()

def test_pipeline_dynamic_backend_resolution():
    """Verify that AuditConfig and IDICOCPipeline resolve configured backends correctly in mock mode."""
    # Postgres configuration
    config_pg = AuditConfig(
        ctm_mode="full",
        ctm_storage_backend="postgres",
        ctm_postgres_uri="postgresql://user:pass@host/db",
        ctm_storage_kwargs={"mock": True},
    )
    pipeline = IDICOCPipeline(config_pg)
    assert isinstance(pipeline.ctm._dag._storage, PostgresCTMStorage)
    assert pipeline.ctm._dag._storage.mock is True

    # DynamoDB configuration
    config_ddb = AuditConfig(
        ctm_mode="full",
        ctm_storage_backend="dynamodb",
        ctm_dynamodb_table="my_table",
        ctm_storage_kwargs={"mock": True},
    )
    pipeline_ddb = IDICOCPipeline(config_ddb)
    assert isinstance(pipeline_ddb.ctm._dag._storage, DynamoDBStorage)
    assert pipeline_ddb.ctm._dag._storage.mock is True

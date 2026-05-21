"""Tests for configurable audit log redirection (not CTM)."""

import json
import logging
import tempfile
from pathlib import Path

import pytest

from iiae.config import IIAEConfig
from iiae.logger import configure_logging, get_logger


@pytest.fixture(autouse=True)
def reset_logging_state():
    import iiae.logger as log_mod

    log_mod._CONFIGURED_DESTINATION = None
    root = logging.getLogger("IIAE")
    root.handlers.clear()
    yield
    root.handlers.clear()
    log_mod._CONFIGURED_DESTINATION = None


def test_stdout_default():
    configure_logging("stdout")
    logger = get_logger("IIAE.Test")
    assert any(isinstance(h, logging.StreamHandler) for h in logging.getLogger("IIAE").handlers)


def test_file_destination_writes_json(tmp_path):
    log_file = tmp_path / "audit.log"
    configure_logging(f"file:{log_file}")
    logger = get_logger("Test.File")
    logger.info("TEST_EVENT", extra={"iiae_data": {"verified": True}})

    content = log_file.read_text(encoding="utf-8")
    record = json.loads(content.strip())
    assert record["message"] == "TEST_EVENT"
    assert record["verified"] is True


def test_none_disables_output(capsys):
    configure_logging("none")
    logger = get_logger("Test.None")
    logger.info("SHOULD_NOT_APPEAR", extra={"iiae_data": {}})
    captured = capsys.readouterr()
    assert "SHOULD_NOT_APPEAR" not in captured.out


def test_iiae_config_applies_log_destination(tmp_path):
    log_file = tmp_path / "cfg.log"
    IIAEConfig(log_destination=f"file:{log_file}")
    logger = get_logger("Supervisor")
    logger.info("FROM_CONFIG", extra={"iiae_data": {"ds": 0.0}})

    assert log_file.exists()
    assert "FROM_CONFIG" in log_file.read_text(encoding="utf-8")


def test_unknown_destination_raises():
    with pytest.raises(ValueError, match="Unknown log_destination"):
        configure_logging("invalid-sink")

import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from idicoc_core.config import AuditConfig
from idicoc_core.api.facade import NotaryClient
from idicoc_core.api.schemas import NotaryAuditResult

def test_audit_config_properties():
    # Instantiating with default values
    config = AuditConfig()
    assert config.correction_base_tolerance == 0.15
    assert config.instance_name == "ai_comercial"
    assert config.enable_hard_halt is False

    # Check warning when enable_hard_halt is set to True
    with pytest.warns(UserWarning, match="enable_hard_halt ha sido forzada a False"):
        config_warn = AuditConfig(enable_hard_halt=True)
    assert config_warn.enable_hard_halt is False


@patch('idicoc_core.dse.evaluator.DissonanceStateEvaluator.evaluate')
def test_notary_client_auditar_success(mock_evaluate):
    mock_evaluate.return_value = (0.05, [], {"d_s": 0.05})
    config = AuditConfig(
        rigidity_epsilon=0.1,
        ctm_mode="disabled",
        dissonance_weights=(0.0, 0.5, 0.4, 0.1, 0.0, 0.0, 0.0)
    )
    client = NotaryClient(config)
    res = client.auditar(
        user_prompt="test prompt",
        rag_context="test context",
        llm_output="test output"
    )
    
    assert isinstance(res, NotaryAuditResult)
    assert res.is_admitted is True
    assert res.dissonance_ds == 0.05
    assert res.violated_policies == []
    assert res.metrics == {"d_s": 0.05}


def test_notary_client_hardware_containment_rejection(monkeypatch):
    monkeypatch.setenv("IIAE_HARDWARE_KEY", "mock_key")
    config = AuditConfig(
        require_hardware_seal=True,  # Force hardware containment check
        ctm_mode="disabled"
    )
    client = NotaryClient(config)
    
    # Since metadata is empty, hardware_contained will be False and it will breach containment stage 2
    res = client.auditar(
        user_prompt="test prompt",
        rag_context="test context",
        llm_output="test output"
    )
    
    assert isinstance(res, NotaryAuditResult)
    assert res.is_admitted is False
    assert res.dissonance_ds == float("inf")
    assert "Stage 2: Hardware Mask Containment Breach" in res.violated_policies

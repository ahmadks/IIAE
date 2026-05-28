import pytest
import numpy as np
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.dse.structural_strategy import StructuralDissonanceStrategy

def test_spsa_dynamic_decay_and_config():
    """Verify SPSA parameter propagation and decay in project method."""
    config = AuditConfig(
        spsa_a=0.5,
        spsa_c=0.01,
        spsa_alpha=0.5,
        spsa_gamma=0.2,
        spsa_decay_enabled=True,
    )
    strategy = StructuralDissonanceStrategy(config=config)
    assert strategy.config.spsa_a == 0.5
    assert strategy.config.spsa_c == 0.01
    assert strategy.config.spsa_alpha == 0.5
    assert strategy.config.spsa_gamma == 0.2
    assert strategy.config.spsa_decay_enabled is True

    y = "test query"
    V_hat = "ideal target response"
    G_t = None
    
    proj = strategy.project(y=y, epsilon=0.1, V_hat=V_hat, G_t=G_t, max_iter=3)
    assert isinstance(proj, np.ndarray)
    assert proj.ndim == 1

def test_spsa_no_decay():
    """Verify SPSA parameter propagation when spsa_decay_enabled is False."""
    config = AuditConfig(
        spsa_a=0.3,
        spsa_c=0.05,
        spsa_decay_enabled=False,
    )
    strategy = StructuralDissonanceStrategy(config=config)
    assert strategy.config.spsa_decay_enabled is False

    y = "test query"
    V_hat = "ideal target response"
    G_t = None
    
    proj = strategy.project(y=y, epsilon=0.1, V_hat=V_hat, G_t=G_t, max_iter=2)
    assert isinstance(proj, np.ndarray)

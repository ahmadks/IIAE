"""
Test file for NotaryClient with logic strategy profile.
Tests the IIAE service integration with logical dissonance measurement via optimal transport.
"""

import math
import numpy as np
import pytest

from idicoc_core.config import AuditConfig
from idicoc_core import NotaryClient
from idicoc_core.dse.evaluator import StructuralDissonanceStrategy


class DummyEmbedder:
    """A deterministic embedding provider for tests."""

    def encode(self, text, model_name=None):
        if isinstance(text, list):
            text = " ".join(str(item) for item in text)
        text_bytes = str(text).encode("utf-8")
        vec = np.zeros(32, dtype=float)
        for idx, byte in enumerate(text_bytes[:32]):
            vec[idx] = float(byte) / 255.0
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0.0 else vec


class MockAuditInput:
    """Mock input that simulates a measure (distribution) for logic strategy."""

    def __init__(self, distribution: np.ndarray, lambda_logic: float = 1.0):
        self.distribution = distribution
        self.lambda_logic = lambda_logic

    def __str__(self):
        return str(self.distribution.tolist())

    def __array__(self, dtype=None):
        return np.asarray(self.distribution, dtype=dtype)


def _build_logic_service(*args, **kwargs):
    return NotaryClient(
        AuditConfig(
            ctm_mode="disabled",
            rigidity_epsilon=0.1,
            policy_loader=None,
            policy_file_path="/tmp/nonexistent_logic_policy_file.txt",
            embedding_provider=DummyEmbedder(),
        )
    )


@pytest.fixture
def logic_service():
    """Create an NotaryClient instance configured for logic mode."""
    return _build_logic_service()


def test_logic_service_with_compatible_distribution(logic_service):
    """The service should admit a compatible numeric distribution."""
    audit_distribution = np.array([0.32, 0.34, 0.34])
    audit_input = MockAuditInput(audit_distribution)

    res = logic_service.audit(
        user_prompt="Mock numeric distribution input",
        rag_context="\n".join([
            "Distribution constraint: must maintain entropy ≥ 1.0",
            "Balance requirement: all mass must be accounted for",
        ]),
        llm_output=str(audit_input.distribution.tolist())
    )

    assert res.is_admitted is True
    assert res.dissonance_ds <= 0.15

def test_logic_service_with_incompatible_distribution():
    """The service should reject a distribution that violates a hard numeric policy."""
    logic_service = _build_logic_service()
    audit_distribution = np.array([-0.5, 0.8, 0.7])
    audit_input = MockAuditInput(audit_distribution)
    policy_input = [
        {
            "id": "ax_negative",
            "text": "No negative weights are allowed",
            "policy_type": "regex",
            "polarity": "negative",
            "hardness": "hard",
            "priority": 10,
            "mode": "numeric",
            "pattern": "-",
        }
    ]

    res = logic_service.audit(
        user_prompt="Incompatible numeric distribution input",
        rag_context="\n".join([
            "Distribution constraint: must be in the probability simplex",
            "All weights must be non-negative",
        ]),
        llm_output=str(audit_input.distribution.tolist()),
        context_policies=policy_input,
    )

    assert res.is_admitted is False
    assert math.isinf(res.dissonance_ds)


def test_logic_service_with_partial_dissonance():
    """The service should report moderate dissonance without forcing correction when within epsilon."""
    logic_service = _build_logic_service()
    audit_distribution = np.array([0.35, 0.32, 0.33])

    res = logic_service.audit(
        user_prompt="Partial dissonance distribution input",
        rag_context="Entropy constraint",
        llm_output=str(audit_distribution.tolist()),
        epsilon_override=0.1,
    )

    assert res.dissonance_ds >= 0.0
    # allowed_epsilon in the result is the effective_threshold =
    # correction_base_tolerance (0.15) + epsilon_override (0.1) = 0.25
    assert res.allowed_epsilon == pytest.approx(0.25)


def test_logic_service_lambda_composition():
    """The service should still compute D_s correctly when no dynamic policies are present."""
    logic_service = _build_logic_service()

    vec = np.array([0.33, 0.33, 0.34])
    res = logic_service.audit(
        user_prompt="Uniform-ish numeric distribution input",
        rag_context="",
        llm_output=str(vec.tolist()),
    )

    assert "d_2" in res.metrics


# =============================================================================
# ADDITIONAL TESTS: SIGNAL SIZE & FREQUENCY LIMITS
# =============================================================================


def test_logic_signal_extreme_size_handling():
    """
    Escenario 3: Límites de tamaño de la señal (dimensión).
    Prueba cómo la estrategia maneja tamaños de entrada extremos (muy pequeños o muy grandes)
    mediante padding o truncamiento dinámico para alinearse al ancla de 4D.
    """
    config = AuditConfig()
    strategy = StructuralDissonanceStrategy(config, lambda_1=1.0)

    # 1. Señal muy pequeña (dimensión 1)
    small_signal = MockAuditInput(np.array([1.0]))
    D_s_small, _, _, _, metrics_small = strategy.compute(
        audit_input=small_signal,
        context_input=[],
        context_policies=[],
    )
    # Se debe haber autopaddeado a 4D ([1.0, 0.0, 0.0, 0.0])
    assert metrics_small["reference_count"] == 4
    # EMD de [1.0, 0.0, 0.0, 0.0] a [0.25, 0.25, 0.25, 0.25] es exactamente 1.5
    assert metrics_small["d_1"] > 0.5

    # 2. Señal muy grande (dimensión 6)
    large_signal = MockAuditInput(np.array([0.1, 0.2, 0.3, 0.4, 0.05, 0.05]))
    D_s_large, _, _, _, metrics_large = strategy.compute(
        audit_input=large_signal,
        context_input=[],
        context_policies=[],
    )
    # Se debe haber truncado a 4D ([0.1, 0.2, 0.3, 0.4] normalizado)
    assert metrics_large["reference_count"] == 4
    assert np.isfinite(D_s_large)


def test_logic_signal_frequency_impulses():
    """
    Escenario 4: Frecuencia de la señal (impulsos vs distribución uniforme).
    Evalúa señales con picos de alta frecuencia (un solo bin con toda la masa)
    frente a señales de baja frecuencia/uniformes, verificando los límites de EMD
    y la detección matemática de colapso de frecuencia.
    """
    config = AuditConfig()
    strategy = StructuralDissonanceStrategy(config, lambda_1=1.0)

    # 1. Impulso puro (alta frecuencia/entropía baja/colapso en un punto)
    high_freq_signal = MockAuditInput(np.array([0.0, 0.0, 1.0, 0.0]))
    _, _, _, correction_high, metrics_high = strategy.compute(
        audit_input=high_freq_signal,
        context_input=[],
        context_policies=[],
    )
    # EMD de [0.0, 0.0, 1.0, 0.0] a [0.25, 0.25, 0.25, 0.25]
    # Cumsum: [0.0, 0.0, 1.0, 1.0] vs [0.25, 0.50, 0.75, 1.00]
    # Diferencias: 0.25 + 0.50 + 0.25 + 0.0 = 1.0
    assert metrics_high["d_1"] > 0.2
    # Al ser un impulso concentrado, supera el umbral de rigidez base y requiere corrección
    assert correction_high is True

    # 2. Distribución casi uniforme (baja frecuencia/baja disonancia)
    low_freq_signal = MockAuditInput(np.array([0.24, 0.26, 0.25, 0.25]))
    _, _, _, correction_low, metrics_low = strategy.compute(
        audit_input=low_freq_signal,
        context_input=[],
        context_policies=[],
    )
    # Disonancia muy baja
    assert metrics_low["d_1"] < 0.05
    assert correction_low is False

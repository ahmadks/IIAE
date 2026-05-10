import pytest
from SLT_Standard_Zero import SLT_StandardZero_Engine, SettlementInput

slt = SLT_StandardZero_Engine(epsilon_threshold=0.4)

def test_electrodomestic_ssppu_suboptimal():
    """DEMO 1: EPR=0.95 < 0.99 → NON-COMPLIANT según este engine"""
    data = SettlementInput(
        nsp=500.0, ssppu_cost=15.0,
        eta_s=95.0, eta_r=5.0, # EPR=0.95
        ds_score=0.3
    )
    r = slt.calculate_settlement(data)
    assert r['tier'] == "1.1 CONSUMER"
    assert r['metrics']['base_type'] == "SSPPU"
    assert r['metrics']['epr'] == pytest.approx(0.95, rel=1e-6)
    assert r['metrics']['coeff_c'] == pytest.approx(0.0095, rel=1e-4) # 0.01 * 0.95
    assert r['financials']['base_royalty'] == pytest.approx(0.1425, rel=1e-4) # 15 * 0.0095
    assert r['status']['standard'] == "NON-COMPLIANT" # Tu engine actual
    assert r['status']['safe_harbor'] == "QUARANTINED"

def test_electric_car_system_level():
    """DEMO 2: System-Level con EPR=0.999 → STANDARD-ZERO"""
    data = SettlementInput(
        nsp=80000.0,
        eta_s=99.9, eta_r=0.1,
        ds_score=0.0,
        system_critical=True,
        trace_id="CAR-MODELS-001"
    )
    r = slt.calculate_settlement(data)
    assert r['tier'] == "1.1 SYSTEM-LEVEL"
    assert r['financials']['base_royalty'] == 800.0
    assert r['status']['standard'] == "STANDARD-ZERO"
    assert r['status']['safe_harbor'] == "ACTIVE"

def test_commercial_ai_tier12_zip():
    """DEMO 3: Tier 1.2 con audit → INFRASTRUCTURE"""
    data = SettlementInput(
        service_revenue=10_000_000.0,
        eta_s=99.8, eta_r=0.2,
        ds_score=0.0,
        margin_t=0.20,
        tier_12_audit=True,
        trace_id="GEMINI-2026-05"
    )
    r = slt.calculate_settlement(data)
    assert r['tier'] == "1.2 INFRASTRUCTURE"
    assert r['financials']['base_royalty'] == 100_000.0
    assert r['financials']['zip_participation'] == 285_000.0
    assert r['status']['standard'] == "STANDARD-ZERO"
    assert r['status']['safe_harbor'] == "ACTIVE"

def test_reversion_rule():
    """DEMO 5: Tier 1.2 sin audit revierte a 1.1 CONSUMER"""
    data = SettlementInput(
        service_revenue=5_000_000.0,
        nsp=50_000_000.0,
        eta_s=99.5, eta_r=0.5,
        ds_score=0.0,
        tier_12_audit=False
    )
    r = slt.calculate_settlement(data)
    assert r['tier'] == "1.1 CONSUMER"
    assert r['metrics']['base_type'] == "NSP-Reverted"
    assert r['financials']['base_royalty'] == 500_000.0
    assert r['status']['standard'] == "STANDARD-ZERO"

def test_zip_voluntary():
    """ZIP=0 si margin_t<=0.01"""
    data = SettlementInput(
        service_revenue=5_000_000, eta_s=99.9, eta_r=0.1, ds_score=0.0,
        margin_t=0.01, tier_12_audit=True
    )
    r = slt.calculate_settlement(data)
    assert r['financials']['zip_participation'] == 0.0

def test_zip_floor_waiver():
    """Sin floor si margen<5%"""
    data = SettlementInput(
        service_revenue=1_000_000, eta_s=99.9, eta_r=0.1, ds_score=0.0,
        margin_t=0.04, tier_12_audit=True
    )
    r = slt.calculate_settlement(data)
    assert r['financials']['zip_participation'] == 4_500.0
    assert r['financials']['zip_floor_applied'] == False

def test_safe_harbor_ds_requirement():
    """Tier 1.2 exige Ds=0 para Safe Harbor"""
    data = SettlementInput(
        service_revenue=1_000_000, eta_s=99.9, eta_r=0.1,
        ds_score=0.01, tier_12_audit=True
    )
    r = slt.calculate_settlement(data)
    assert r['status']['safe_harbor'] == "QUARANTINED"
    assert "REQUIRES_DS_ZERO" in r['compliance']['safe_harbor_reason']

def test_ctm_seal_structure():
    """CTM seal existe"""
    data = SettlementInput(nsp=1000, eta_s=99, eta_r=1, ds_score=0.1, trace_id="TEST123")
    r = slt.calculate_settlement(data)
    assert len(r['compliance']['ctm_seal']) == 64
    assert r['compliance']['ctm_block']['trace_id'] == "TEST123"
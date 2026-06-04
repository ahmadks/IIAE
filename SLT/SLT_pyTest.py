import pytest
from SLT.SLT_Standard_Zero import SLTStandardZeroEngine, SettlementInput

slt = SLTStandardZeroEngine(epsilon_threshold=0.4)


# ===================================================================
# DEMO 1: APPLIANCE (Tier 1.1 SSPPU, Black-Box)
# ===================================================================
def test_appliance_ssppu_blackbox():
    """EPR=0.95 → sub-Standard-Zero → IIAE-COMPLIANT (BLACK-BOX), No Safe Harbor."""
    data = SettlementInput(
        nsp=500.0,
        ssppu_cost=15.0,  # IIAE chip cost $15
        y_total=100.0,
        y_valid=95.0,  # EPR = 0.95
        ds_score=0.3,
    )
    r = slt.calculate_settlement(data)

    # Tier & base
    assert r["tier"] == "1.1 CONSUMER"
    assert r["metrics"]["base_type"] == "SSPPU"
    assert r["metrics"]["base_value"] == 15.0

    # Metrics
    assert r["metrics"]["epr"] == pytest.approx(0.95, rel=1e-6)
    assert r["metrics"]["coeff_c"] == 0.01  # C fixed, non-degrading now

    # Financials
    assert r["financials"]["base_royalty"] == pytest.approx(0.15, rel=1e-4)  # 15 * 0.01
    assert r["financials"]["zip_participation"] == 0.0
    assert r["financials"]["total_settlement"] == pytest.approx(0.15, rel=1e-4)

    # Status
    assert r["status"]["standard"] == "IIAE-COMPLIANT (BLACK-BOX)"
    assert r["status"]["safe_harbor"] == "UNAVAILABLE (SOLE LIABILITY)"
    assert r["status"]["certified_auditable"] is False
    assert r["status"]["hardware_anchored"] is False
    assert r["status"]["tier_12_eligible"] is False


# ===================================================================
# DEMO 2: ELECTRIC CAR (System-Level, Ds=0, Black-Box)
# ===================================================================
def test_electric_car_system_level():
    """System-Level with EPR=0.999, Ds=0 → IIAE-COMPLIANT (BLACK-BOX)."""
    data = SettlementInput(
        nsp=80_000.0,
        y_total=1000.0,
        y_valid=999.0,  # EPR ≈ 0.999
        ds_score=0.0,
        system_critical=True,
        trace_id="CAR-MODELS-001",
    )
    r = slt.calculate_settlement(data)

    # Tier & base
    assert r["tier"] == "1.1 SYSTEM-LEVEL"
    assert r["metrics"]["base_type"] == "NSP-System"
    assert r["metrics"]["base_value"] == 80_000.0

    # Financials
    assert r["financials"]["base_royalty"] == 800.0
    assert r["financials"]["zip_participation"] == 0.0
    assert r["financials"]["total_settlement"] == 800.0

    # Status
    assert r["status"]["standard"] == "IIAE-COMPLIANT (BLACK-BOX)"
    assert r["status"]["safe_harbor"] == "UNAVAILABLE (SOLE LIABILITY)"
    assert r["status"]["certified_auditable"] is False
    assert r["status"]["hardware_anchored"] is False


# ===================================================================
# DEMO 3: COMMERCIAL AI (Tier 1.2, Hardware-Anchored, ZIP)
# ===================================================================
def test_commercial_ai_hardware_anchored_zip():
    """Tier 1.2 + Hardware Anchoring + Ds=0 → FULL SAFE HARBOR."""
    data = SettlementInput(
        service_revenue=10_000_000.0,
        y_total=1000.0,
        y_valid=998.0,  # EPR ≈ 0.998
        ds_score=0.0,
        margin_t=0.20,
        tier_12_audit=True,
        hardware_anchored=True,
        trace_id="GEMINI-2026-05",
    )
    r = slt.calculate_settlement(data)

    # Tier & base
    assert r["tier"] == "1.2 INFRASTRUCTURE"
    assert r["metrics"]["base_type"] == "Integrity-Certified Revenue"
    assert r["metrics"]["base_value"] == 10_000_000.0

    # Financials
    assert r["financials"]["base_royalty"] == 100_000.0
    assert r["financials"]["zip_participation"] == 285_000.0
    # zip_raw (285,000) > floor (95,000) → floor NOT applied (raw already exceeds floor)
    assert r["financials"]["zip_floor_applied"] is False
    assert r["financials"]["total_settlement"] == 385_000.0

    # Status
    assert r["status"]["standard"] == "IIAE-CERTIFIED (HARDWARE-ANCHORED)"
    assert r["status"]["safe_harbor"] == "FULL_SAFE_HARBOR (HARDWARE-ANCHORED)"
    assert r["status"]["certified_auditable"] is True
    assert r["status"]["hardware_anchored"] is True
    assert r["status"]["tier_12_eligible"] is True


# ===================================================================
# DEMO 4: REVERSION RULE (Tier 1.2 declared, no audit)
# ===================================================================
def test_reversion_rule():
    """Tier 1.2 sin audit → revierte a Tier 1.1 CONSUMER."""
    data = SettlementInput(
        service_revenue=5_000_000.0,
        nsp=50_000_000.0,
        y_total=1000.0,
        y_valid=995.0,
        ds_score=0.0,
        tier_12_audit=False,
    )
    r = slt.calculate_settlement(data)

    # Tier & base
    assert r["tier"] == "1.1 CONSUMER"
    assert r["metrics"]["base_type"] == "NSP-Reverted"
    assert r["metrics"]["base_value"] == 50_000_000.0

    # Financials
    assert r["financials"]["base_royalty"] == 500_000.0
    assert r["financials"]["zip_participation"] == 0.0

    # Status
    assert r["status"]["standard"] == "IIAE-COMPLIANT (BLACK-BOX)"
    assert r["status"]["safe_harbor"] == "UNAVAILABLE (SOLE LIABILITY)"


# ===================================================================
# DEMO 5: SOFTWARE-CERTIFIED (Tier 1.2, Auditable, No Hardware)
# ===================================================================
def test_software_certified_limited_safe_harbor():
    """Tier 1.2 + Audit + No Hardware → LIMITED SAFE HARBOR."""
    data = SettlementInput(
        service_revenue=1_000_000.0,
        y_total=1000.0,
        y_valid=995.0,
        ds_score=0.02,
        margin_t=0.12,
        tier_12_audit=True,
        hardware_anchored=False,
        trace_id="SAAS-CERTIFIED-001",
    )
    r = slt.calculate_settlement(data)

    # Tier & base
    assert r["tier"] == "1.2 INFRASTRUCTURE"
    assert r["metrics"]["base_type"] == "Integrity-Certified Revenue"
    assert r["metrics"]["base_value"] == 1_000_000.0

    # Financials
    assert r["financials"]["base_royalty"] == 10_000.0
    assert r["financials"]["zip_participation"] == 16_500.0
    # zip_raw (16,500) > floor (55,000 * 0.05? NO)
    # surplus_value = 0.11 * 1M = 110,000. floor_min = 110,000 * 0.05 = 5,500
    # zip_raw = 16,500 > 5,500 → floor NOT applied
    assert r["financials"]["zip_floor_applied"] is False
    assert r["financials"]["total_settlement"] == 26_500.0

    # Status
    assert r["status"]["standard"] == "IIAE-CERTIFIED (SOFTWARE)"
    assert r["status"]["safe_harbor"] == "LIMITED_SAFE_HARBOR (SOFTWARE-CERTIFIED)"
    assert r["status"]["certified_auditable"] is True
    assert r["status"]["hardware_anchored"] is False
    assert r["status"]["tier_12_eligible"] is True


# ===================================================================
# DEMO 6: ZIP VOLUNTARY (margin_t <= C)
# ===================================================================
def test_zip_voluntary():
    """ZIP=0 si margin_t <= 0.01."""
    data = SettlementInput(
        service_revenue=5_000_000,
        y_total=1000.0,
        y_valid=999.0,
        ds_score=0.0,
        margin_t=0.01,
        tier_12_audit=True,
    )
    r = slt.calculate_settlement(data)
    assert r["financials"]["zip_participation"] == 0.0


# ===================================================================
# DEMO 7: ZIP FLOOR WAIVER (FRAND Exception)
# ===================================================================
def test_zip_floor_waiver():
    """Sin floor si margen < 5%."""
    data = SettlementInput(
        service_revenue=1_000_000,
        y_total=1000.0,
        y_valid=999.0,
        ds_score=0.0,
        margin_t=0.04,
        tier_12_audit=True,
    )
    r = slt.calculate_settlement(data)
    # Surplus margin = 0.04 - 0.01 = 0.03 (3%)
    # ZIP raw = 0.15 * 0.03 * 1M = 4,500
    # Floor NOT applied because 3% < 5%
    assert r["financials"]["zip_participation"] == 4_500.0
    assert r["financials"]["zip_floor_applied"] is False


# ===================================================================
# DEMO 8: SAFE HARBOR REQUIRES Ds=0 FOR TIER 1.2 HARDWARE
# ===================================================================
def test_safe_harbor_ds_requirement():
    """Tier 1.2 Hardware-Anchored exige Ds=0 para Full Safe Harbor."""
    data = SettlementInput(
        service_revenue=1_000_000,
        y_total=1000.0,
        y_valid=999.0,
        ds_score=0.01,  # Ds > 0 → no Full Safe Harbor
        tier_12_audit=True,
        hardware_anchored=True,
    )
    r = slt.calculate_settlement(data)
    assert r["status"]["safe_harbor"] == "PENDING_Ds_STABILIZATION"
    assert "AUDITABLE_BUT_DRIFTING" in r["compliance"]["safe_harbor_reason"]


# ===================================================================
# DEMO 9: SYSTEM-LEVEL REJECTS SSPPU
# ===================================================================
def test_system_level_rejects_ssppu():
    """System-Level + SSPPU → ValueError al calcular settlement."""
    data = SettlementInput(
        nsp=50_000,
        ssppu_cost=100,  # ❌ SSPPU not allowed for critical-system
        system_critical=True,
    )
    with pytest.raises(ValueError, match="SSPPU is not allowed"):
        slt.calculate_settlement(data)  # ← El error se lanza AQUÍ, no en el constructor


# ===================================================================
# DEMO 10: CTM SEAL STRUCTURE
# ===================================================================
def test_ctm_seal_structure():
    """CTM seal existe y tiene 64 caracteres (SHA-256)."""
    data = SettlementInput(
        nsp=1000,
        y_total=100.0,
        y_valid=99.0,
        ds_score=0.1,
        trace_id="TEST123",
    )
    r = slt.calculate_settlement(data)
    assert len(r["compliance"]["ctm_seal"]) == 64
    assert r["compliance"]["ctm_block"]["trace_id"] == "TEST123"


# ===================================================================
# DEMO 11: HARDWARE-ANCHORED FLAG PROPAGATION
# ===================================================================
def test_hardware_anchored_flag_propagation():
    """El flag hardware_anchored se propaga correctamente al reporte."""
    data = SettlementInput(
        service_revenue=500_000,
        y_total=1000.0,
        y_valid=999.0,
        ds_score=0.0,
        tier_12_audit=True,
        hardware_anchored=True,
    )
    r = slt.calculate_settlement(data)
    assert r["status"]["hardware_anchored"] is True
    assert r["compliance"]["ctm_block"]["hardware_anchored"] is True
    assert "HARDWARE-ANCHORED" in r["status"]["safe_harbor"]

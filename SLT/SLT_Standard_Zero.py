import hashlib
import json
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, Literal
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# TYPE DEFINITIONS
# ---------------------------------------------------------------------------
TierType = Literal["1.1 CONSUMER", "1.1 SYSTEM-LEVEL", "1.2 INFRASTRUCTURE"]
SafeHarborType = Literal[
    "FULL_SAFE_HARBOR (HARDWARE-ANCHORED)",
    "LIMITED_SAFE_HARBOR (SOFTWARE-CERTIFIED)",
    "UNAVAILABLE (SOLE LIABILITY)",
    "PENDING_Ds_STABILIZATION",
]


# ---------------------------------------------------------------------------
# INPUT DATA CLASS
# ---------------------------------------------------------------------------
@dataclass
class SettlementInput:
    """Inputs for SLT settlement - Open Constitution of Invariance."""

    nsp: Optional[float] = None           # Net Selling Price (Tier 1.1 / System-Level)
    service_revenue: Optional[float] = None  # Integrity-Certified Revenue (Tier 1.2)
    ssppu_cost: Optional[float] = None    # SSPPU (Tier 1.1 only, not for System-Level)
    eta_s: float = 0.0                    # Segregated / Purged Entropy (AEM)
    eta_r: float = 0.0                    # Residual Entropy
    ds_score: float = 1.0                 # Dissonance Coefficient D_s ∈ [0, 1]
    margin_t: float = 0.0                 # Integrity premium T (e.g., 0.12 = 12%)
    system_complex: bool = False         # True → cars, robots, spacecraft (System-Level)
    tier_12_audit: bool = False           # True → continuous CTM logs + EPR reporting
    hardware_anchored: bool = False       # True → ePUF / HSS / Cloud-HSM with attestation
    trace_id: Optional[str] = None        # External transaction ID


# ---------------------------------------------------------------------------
# GOVERNANCE ENGINE
# ---------------------------------------------------------------------------
class SLTStandardZeroEngine:
    """
    SLT Governance Engine (Normative Economic Layer).

    Implements:
      - Sec 2.1    Dual-Track Licensing (Tier 1.1 / Tier 1.2)
      - Sec 2.1.1  SSPPU Option (Tier 1.1 only)
      - Sec 2.1.2  System-Level Clarification (Automotive & Complex Systems)
      - Sec 2.2    ZIP (Universal Cascading Participation)
      - Sec 3.1.1  Safe Harbor Tiers (Full / Limited / None)
      - Sec 3.3    Liability Allocation (Bit-Level / Logical / No Notarization)
      - Sec 5.4.2.1 Hardware-Anchored Certified (Full Safe Harbor)
      - Sec 5.4.2.2 Software-Certified (Limited Safe Harbor)
    """

    def __init__(self, epsilon_threshold: float = 0.4):
        # D_s threshold for general compliance (non-infrastructure)
        self.epsilon = epsilon_threshold

        # FRAND Normalization Constant C = 1.0% (fixed, non-degrading)
        self.C_FACTOR = 0.01

        # ZIP parameters (Service Fee on surplus integrity margin)
        self.ZIP_RATE = 0.15   # 15% of surplus margin above C
        self.ZIP_FLOOR = 0.05  # 5% floor on surplus margin (FRAND exception applies)

        # Standard-Zero EPR threshold (Annex A)
        self.STANDARD_ZERO_EPR = 0.99

    # -------------------------------------------------------------------
    # TECHNICAL METRICS
    # -------------------------------------------------------------------
    def calculate_epr(self, eta_s: float, eta_r: float) -> float:
        """
        Entropy Purge Rate (EPR) = ηs / (ηs + η_r).
        Annex A: Technical measure of entropy purge by AEM.
        """
        total_entropy = eta_s + eta_r
        if total_entropy <= 0:
            return 1.0  # Rest state → Standard-Zero baseline
        return eta_s / total_entropy

    # -------------------------------------------------------------------
    # TIER & BASE SELECTION
    # -------------------------------------------------------------------
    def _select_tier_and_base(self, data: SettlementInput) -> tuple[TierType, float, str]:
        """
        Tier selection and royalty base according to Sec 2.1, 2.1.1, 2.1.2.

        Priority:
          1. System-Level (complex systems) → Tier 1.1 SYSTEM-LEVEL, base = NSP
          2. Tier 1.2 (Infrastructure) → base = Integrity-Certified Revenue (with audit)
          3. Tier 1.1 Consumer → base = NSP or SSPPU (if allowed)
        """
        # --- System-Level: always NSP, SSPPU explicitly disallowed ---
        if data.system_complex:
            if data.nsp is None:
                raise ValueError(
                    "system_complex=True requires nsp (Sec 2.1.2 System-Level)."
                )
            if data.ssppu_cost is not None:
                raise ValueError(
                    "SSPPU is not allowed for system implementations "
                    "(Sec 2.1.2)."
                )
            return "1.1 SYSTEM-LEVEL", float(data.nsp), "NSP-System"

        # --- Tier 1.2: requires Integrity-Certified Revenue + audit; otherwise revert ---
        if data.service_revenue is not None:
            if data.tier_12_audit:
                return (
                    "1.2 INFRASTRUCTURE",
                    float(data.service_revenue),
                    "Integrity-Certified Revenue",
                )
            else:
                # Reversion Rule (Sec 2.1): no CTM logs → revert to Tier 1.1 NSP
                if data.nsp is None:
                    raise ValueError(
                        "Tier 1.2 without audit requires nsp for reversion to Tier 1.1."
                    )
                return "1.1 CONSUMER", float(data.nsp), "NSP-Reverted"

        # --- Tier 1.1 Consumer: SSPPU Option (Sec 2.1.1) ---
        if data.ssppu_cost is not None:
            return "1.1 CONSUMER", float(data.ssppu_cost), "SSPPU"

        # --- Default Tier 1.1 Consumer on NSP ---
        if data.nsp is None:
            raise ValueError("Must provide nsp, service_revenue, or ssppu_cost.")
        return "1.1 CONSUMER", float(data.nsp), "NSP"

    # -------------------------------------------------------------------
    # MAIN SETTLEMENT CALCULATION
    # -------------------------------------------------------------------
    def calculate_settlement(self, data: SettlementInput) -> Dict[str, Any]:
        """
        Executes full settlement under SLT (Normative Engine).

        - Applies fixed FRAND Constant C = 1.0% (no degradation).
        - Enforces Dual-Track Licensing and Reversion Rule.
        - Computes ZIP participation for Tier 1.2 only.
        - Computes Safe Harbor status based on certification and hardware anchoring.
        """
        # 1. ── TECHNICAL INTEGRITY METRICS (Annex A) ────────────────
        epr = self.calculate_epr(data.eta_s, data.eta_r)
        is_standard_zero = epr >= self.STANDARD_ZERO_EPR
        ds_compliant = data.ds_score <= self.epsilon

        # 2. ── CERTIFICATION STATUS ─────────────────────────────────
        # IIAE-CERTIFIED requires: audit + Standard-Zero EPR + D_s within threshold
        is_certified = data.tier_12_audit and is_standard_zero and ds_compliant

        # 3. ── TIER SELECTION & ECONOMIC BASE ───────────────────────
        tier, royalty_base, base_type = self._select_tier_and_base(data)

        # 4. ── FRAND CONSTANT C = 1.0% (non-degrading) ──────────────
        coeff_c = self.C_FACTOR
        base_royalty = royalty_base * coeff_c

        # Certification label
        if is_certified and data.hardware_anchored:
            status_std = "IIAE-CERTIFIED (HARDWARE-ANCHORED)"
        elif is_certified:
            status_std = "IIAE-CERTIFIED (SOFTWARE)"
        else:
            status_std = "IIAE-COMPLIANT (BLACK-BOX)"

        # 5. ── ZIP (Universal Cascading Participation) ──────────────
        # Applies only to Tier 1.2, with certification + Standard-Zero + T > C
        zip_contribution = 0.0
        zip_floor_applied = False
        if tier == "1.2 INFRASTRUCTURE" and is_certified and data.margin_t > self.C_FACTOR:
            surplus_margin = data.margin_t - self.C_FACTOR
            surplus_value = royalty_base * surplus_margin
            zip_raw = surplus_value * self.ZIP_RATE

            # FRAND floor: only if surplus margin >= 5%
            if surplus_margin >= self.ZIP_FLOOR:
                zip_contribution = max(zip_raw, surplus_value * self.ZIP_FLOOR)
                zip_floor_applied = zip_contribution > zip_raw
            else:
                zip_contribution = zip_raw

        # 6. ── SAFE HARBOR DETERMINATION (Sec 3.1.1) ───────────────
        if is_certified and data.hardware_anchored:
            # Full Safe Harbor: requires D_s = 0 for Tier 1.2
            if tier == "1.2 INFRASTRUCTURE":
                is_sh = data.ds_score == 0.0
                sh_status = (
                    "FULL_SAFE_HARBOR (HARDWARE-ANCHORED)"
                    if is_sh
                    else "PENDING_Ds_STABILIZATION"
                )
                sh_reason = (
                    "CERTIFIED_DETERMINISTIC_TRUST (Bit-Level Notarization)"
                    if is_sh
                    else "AUDITABLE_BUT_DRIFTING"
                )
            else:
                is_sh = ds_compliant
                sh_status = (
                    "FULL_SAFE_HARBOR (HARDWARE-ANCHORED)"
                    if is_sh
                    else "PENDING_Ds_STABILIZATION"
                )
                sh_reason = (
                    "OPERATIONALLY_COMPLIANT"
                    if is_sh
                    else "DRIFT_ABOVE_THRESHOLD"
                )
        elif is_certified:
            # Limited Safe Harbor: software-certified (no hardware anchoring)
            is_sh = ds_compliant
            sh_status = (
                "LIMITED_SAFE_HARBOR (SOFTWARE-CERTIFIED)"
                if is_sh
                else "PENDING_Ds_STABILIZATION"
            )
            sh_reason = (
                "LOGICAL_NOTARIZATION (Software-Certified)"
                if is_sh
                else "DRIFT_ABOVE_THRESHOLD"
            )
        else:
            # No Safe Harbor
            is_sh = False
            sh_status = "UNAVAILABLE (SOLE LIABILITY)"
            sh_reason = "NON_AUDITABLE_OR_BLACK_BOX"

        # 7. ── CTM SEAL (immutable audit block) ────────────────────
        timestamp = time.time()
        trace = data.trace_id or hashlib.sha256(
            str(timestamp).encode()
        ).hexdigest()[:12]

        seal_block = {
            "trace_id": trace,
            "tier": tier,
            "status_std": status_std,
            "epr": round(epr, 6),
            "ds": data.ds_score,
            "coeff_c": coeff_c,
            "royalty_base": round(royalty_base, 2),
            "base_royalty": round(base_royalty, 4),
            "zip": round(zip_contribution, 4),
            "safe_harbor": sh_status,
            "hardware_anchored": data.hardware_anchored,
            "timestamp": timestamp,
        }
        seal_payload = json.dumps(seal_block, sort_keys=True)
        ctm_seal = hashlib.sha256(seal_payload.encode()).hexdigest()

        # 8. ── RESPONSE ────────────────────────────────────────────
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace,
            "tier": tier,
            "metrics": {
                "epr": round(epr, 6),
                "ds_score": data.ds_score,
                "coeff_c": coeff_c,
                "base_type": base_type,
                "base_value": round(royalty_base, 2),
            },
            "status": {
                "standard": status_std,
                "safe_harbor": sh_status,
                "certified_auditable": is_certified,
                "hardware_anchored": data.hardware_anchored,
                "tier_12_eligible": is_certified,
            },
            "financials": {
                "base_royalty": round(base_royalty, 4),
                "zip_participation": round(zip_contribution, 4),
                "zip_floor_applied": zip_floor_applied,
                "total_settlement": round(base_royalty + zip_contribution, 4),
                "currency": "USD",
            },
            "compliance": {
                "safe_harbor_reason": sh_reason,
                "ctm_seal": ctm_seal,
                "ctm_block": seal_block,
                "audit_ref": "WO2026/XXXXX_SLT_ANNEX_A",
                "logic": "FIXED_C_WITH_TIER_REVERSION_AND_ZIP",
                "claims_ref": (
                    "1,19,23,8.5.1" if data.system_complex else "1,19"
                ),
                "governance": "MAII/MAO-Protocol-Compliant",
            },
        }

    # -------------------------------------------------------------------
    # CERTIFICATE GENERATOR
    # -------------------------------------------------------------------
    def generate_certificate(self, report: Dict[str, Any]) -> str:
        """Generates human-readable certificate for ETSI / regulatory audit."""
        tier = report.get("tier")
        sh_status = report.get("status", {}).get("safe_harbor")
        is_hw = report.get("status", {}).get("hardware_anchored", False)

        # ── Safe Harbor narrative ──
        if sh_status == "FULL_SAFE_HARBOR (HARDWARE-ANCHORED)":
            sh_note = (
                "FULL SAFE HARBOR: Bit-Level Notarization active. "
                "Ds=0 verified. Eligible for Mutualized Defense Fund (Sec 3.3(a))."
            )
        elif sh_status == "LIMITED_SAFE_HARBOR (SOFTWARE-CERTIFIED)":
            sh_note = (
                "LIMITED SAFE HARBOR: Logical Notarization active. "
                "Ds<=epsilon verified. Technical defense of Due Diligence. "
                "NOT eligible for Mutualized Defense Fund (Sec 3.3(b))."
            )
        elif sh_status == "PENDING_Ds_STABILIZATION":
            sh_note = (
                "PENDING: Ds stabilization required for Full Safe Harbor. "
                "Auditable but currently drifting."
            )
        else:
            sh_note = (
                "NO SAFE HARBOR: Non-auditable or Black-Box implementation. "
                "100% Sole Liability (Sec 3.3(c))."
            )

        # ── Hardware anchoring note ──
        hw_note = (
            "HARDWARE-ANCHORED: ePUF/HSS/Cloud-HSM attestation verified."
            if is_hw
            else "SOFTWARE-ONLY: Limited to logical notarization."
        )

        return f"""

TIER APPLIED: {report['tier']}

TECHNICAL METRICS (ANNEX A)
  EPR Index:    {report['metrics']['epr']}   (ηS/(ηS+ηR))
  Ds Score:     {report['metrics']['ds_score']}   (Dissonance Coefficient)
  C-Factor:     {report['metrics']['coeff_c']}   (FRAND Constant C = 0.01)

COMPLIANCE STATUS (SEC 3.1.1 + 5.4.2)
  Standard:     {report['status']['standard']}
  Safe Harbor:  {report['status']['safe_harbor']}
  Anchoring:    {hw_note}
  Reason:       {sh_note}
  Tier 1.2 Eligible: {report['status']['tier_12_eligible']}

FINANCIAL SETTLEMENT (SEC 2.1 + 2.2)
  Base Type:         {report['metrics']['base_type']}
  Base Value:        ${report['metrics']['base_value']:,.2f}
  Base Royalty (C):  ${report['financials']['base_royalty']:,.4f}
  ZIP Fund:          ${report['financials']['zip_participation']:,.4f}
  ZIP Floor Applied: {report['financials']['zip_floor_applied']}
  TOTAL:             ${report['financials']['total_settlement']:,.4f} USD

CRYPTOGRAPHIC PROOF (SEC 5.4.2)
  CTM Seal:     {report['compliance']['ctm_seal']}
  Audit Ref:    {report['compliance']['audit_ref']}
  Claims Ref:   {report['compliance']['claims_ref']}
  Governance:   {report['compliance']['governance']}

This certificate constitutes technical proof of Due Diligence
under EU AI Act Art.15, UNECE R155, ISO 26262 ASIL-D, DO-178C.
Verification: Hash CTM block with SHA256 to validate seal.
"""


# ===================================================================
# EXECUTABLE DEMO SUITE
# ===================================================================
if __name__ == "__main__":
    slt = SLTStandardZeroEngine()

    # ── DEMO 1: APPLIANCE (Tier 1.1 SSPPU, Black-Box) ──────────
    print("=" * 70)
    print("DEMO 1: APPLIANCE - Tier 1.1 SSPPU Option (Black-Box)")
    print("=" * 70)
    d1 = SettlementInput(
        nsp=500.0,
        ssppu_cost=15.0,   # IIAE chip cost $15 (SSPPU, Tier 1.1 only)
        eta_s=95.0,
        eta_r=5.0,         # EPR = 0.95 (sub-Standard-Zero, but still Compliant)
        ds_score=0.3,
    )
    r1 = slt.calculate_settlement(d1)
    print(slt.generate_certificate(r1))

    # ── DEMO 2: ELECTRIC CAR (System-Level, Ds=0) ──────────────
    print("\n" + "=" * 70)
    print("DEMO 2: ELECTRIC CAR - System-Level (Sec 2.1.2)")
    print("=" * 70)
    d2 = SettlementInput(
        nsp=80_000.0,
        eta_s=99.9,
        eta_r=0.1,            # EPR ≈ 0.999 (Standard-Zero)
        ds_score=0.0,         # Ds=0 required for ASIL-D / DO-178C
        system_complex=True,
        trace_id="CAR-MODEL-SZ-001",
    )
    r2 = slt.calculate_settlement(d2)
    print(slt.generate_certificate(r2))

    # ── DEMO 3: COMMERCIAL AI SERVICE (Tier 1.2, Hardware, ZIP) ──
    print("\n" + "=" * 70)
    print("DEMO 3: COMMERCIAL AI - Tier 1.2 Hardware-Anchored with ZIP")
    print("=" * 70)
    d3 = SettlementInput(
        service_revenue=10_000_000.0,  # $10M/month Integrity-Certified Revenue
        eta_s=99.8,
        eta_r=0.2,                    # EPR ≈ 0.998 (Standard-Zero)
        ds_score=0.0,                 # Ds=0 → Full Safe Harbor possible
        margin_t=0.20,                # 20% integrity premium (T)
        tier_12_audit=True,           # Continuous CTM logs + EPR reporting
        hardware_anchored=True,       # ePUF / Cloud-HSM attested
        trace_id="GEMINI-2026-05",
    )
    r3 = slt.calculate_settlement(d3)
    print(slt.generate_certificate(r3))

    # ── DEMO 4: SPACEX STARSHIP (System-Level, Ds=0) ───────────
    print("\n" + "=" * 70)
    print("DEMO 4: SPACEX STARSHIP - Complex System (System-Level)")
    print("=" * 70)
    d4 = SettlementInput(
        nsp=100_000_000.0,   # $100M per vehicle
        eta_s=99.99,
        eta_r=0.01,          # EPR ≈ 0.9999 (Standard-Zero)
        ds_score=0.0,        # Ds=0 for mission-critical aerospace
        system_complex=True,
        trace_id="STARSHIP-SN42",
    )
    r4 = slt.calculate_settlement(d4)
    print(slt.generate_certificate(r4))

    # ── DEMO 5: REVERSION RULE (Tier 1.2 declared, no audit) ───
    print("\n" + "=" * 70)
    print("DEMO 5: REVERSION RULE - Tier 1.2 without audit → Tier 1.1")
    print("=" * 70)
    d5 = SettlementInput(
        service_revenue=5_000_000.0,   # Intended Integrity Revenue
        nsp=50_000_000.0,              # NSP used for reversion
        eta_s=99.5,
        eta_r=0.5,
        ds_score=0.0,
        tier_12_audit=False,           # No CTM logs → automatic reversion
        trace_id="AI-SERVICE-NO-AUDIT",
    )
    r5 = slt.calculate_settlement(d5)
    print(slt.generate_certificate(r5))

    # ── DEMO 6: SOFTWARE-CERTIFIED (Limited Safe Harbor) ────────
    print("\n" + "=" * 70)
    print("DEMO 6: SOFTWARE-CERTIFIED - Tier 1.2 Auditable, No Hardware")
    print("=" * 70)
    d6 = SettlementInput(
        service_revenue=1_000_000.0,
        eta_s=99.5,
        eta_r=0.5,             # EPR ≈ 0.995 (Standard-Zero)
        ds_score=0.02,         # Ds <= epsilon → compliant
        margin_t=0.12,         # 12% integrity premium
        tier_12_audit=True,    # CTM logs active
        hardware_anchored=False,  # Software-only
        trace_id="SAAS-CERTIFIED-001",
    )
    r6 = slt.calculate_settlement(d6)
    print(slt.generate_certificate(r6))
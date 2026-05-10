import hashlib
import json
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, Literal
from datetime import datetime, timezone

TierType = Literal["1.1 CONSUMER", "1.1 SYSTEM-LEVEL", "1.2 INFRASTRUCTURE"]


@dataclass
class SettlementInput:
    """Inputs for SLT v3.3 settlement - Open Constitution of Invariance"""
    nsp: Optional[float] = None              # Net Selling Price for Tier 1.1 / System-Level
    service_revenue: Optional[float] = None  # Integrity-Certified Revenue for Tier 1.2
    ssppu_cost: Optional[float] = None       # Smallest Saleable Patent Practicing Unit (Tier 1.1 only)
    eta_s: float = 0.0                       # Segregated / Purged Entropy (AEM)
    eta_r: float = 0.0                       # Residual Entropy
    ds_score: float = 1.0                    # Dissonance Coefficient D_s ∈ [0,1]
    margin_t: float = 0.0                    # Integrity premium T over baseline (e.g. 0.12 = 12%)
    system_critical: bool = False            # True: cars, robots, spacecraft. Triggers System-Level rule
    tier_12_audit: bool = False              # True: continuous CTM logs + EPR reporting (Tier 1.2)
    trace_id: Optional[str] = None           # External transaction ID


class SLT_StandardZero_Engine:
    """
    SLT v3.3 Governance Engine (Normative Economic Layer)

    Implements:
      - Sec 2.1 Dual-Track Licensing (Tier 1.1 / Tier 1.2)
      - Sec 2.1.1 SSPPU Option (Tier 1.1 only)
      - Sec 2.1.2 System-Level Clarification
      - Sec 2.2 ZIP (Universal Cascading Participation)
      - Sec 3.1 / 3.3 Safe Harbor & Liability Allocation
      - Annex A: EPR / D_s as technical metrics (used for certification logic)
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

    def calculate_epr(self, eta_s: float, eta_r: float) -> float:
        """
        Entropy Purge Rate (EPR) = η_s / (η_s + η_r)
        Annex A: Technical measure of entropy purge by AEM.
        """
        total_entropy = eta_s + eta_r
        if total_entropy <= 0:
            # Rest state: no entropy processed → treat as Standard-Zero baseline
            return 1.0
        return eta_s / total_entropy

    def _select_tier_and_base(self, data: SettlementInput) -> tuple[TierType, float, str]:
        """
        Tier selection and royalty base according to Sec 2.1, 2.1.1, 2.1.2.

        Priority:
          1. System-Level (critical systems) → Tier 1.1 SYSTEM-LEVEL, base = NSP
          2. Tier 1.2 (Infrastructure) → base = Integrity-Certified Revenue (with audit)
          3. Tier 1.1 Consumer → base = NSP or SSPPU (if allowed)
        """
        # System-Level: always NSP, SSPPU explicitly disallowed for critical systems
        if data.system_critical:
            if data.nsp is None:
                raise ValueError("system_critical=True requires nsp (Sec 2.1.2 System-Level).")
            if data.ssppu_cost is not None:
                raise ValueError("SSPPU is not allowed for system-critical implementations (Sec 2.1.2).")
            return "1.1 SYSTEM-LEVEL", float(data.nsp), "NSP-System"

        # Tier 1.2: requires Integrity-Certified Revenue + audit; otherwise revert to Tier 1.1
        if data.service_revenue is not None:
            if data.tier_12_audit:
                return "1.2 INFRASTRUCTURE", float(data.service_revenue), "Integrity-Certified Revenue"
            else:
                # Reversion Rule: no CTM logs → revert to Tier 1.1 NSP
                if data.nsp is None:
                    raise ValueError("Tier 1.2 without audit requires nsp for reversion to Tier 1.1.")
                return "1.1 CONSUMER", float(data.nsp), "NSP-Reverted"

        # Tier 1.1 Consumer: SSPPU Option (Sec 2.1.1) if not system-critical
        if data.ssppu_cost is not None:
            return "1.1 CONSUMER", float(data.ssppu_cost), "SSPPU"

        # Default Tier 1.1 Consumer on NSP
        if data.nsp is None:
            raise ValueError("Must provide nsp, service_revenue, or ssppu_cost.")
        return "1.1 CONSUMER", float(data.nsp), "NSP"

    def calculate_settlement(self, data: SettlementInput) -> Dict[str, Any]:
        """
        Executes full settlement under SLT v3.3 (Normative Engine).

        - Applies fixed FRAND Constant C = 1.0% (no degradation).
        - Enforces Dual-Track Licensing and Reversion Rule.
        - Computes ZIP participation for Tier 1.2 only.
        - Computes Safe Harbor status based on certification and D_s.
        """
        # 1. Technical integrity metrics (Annex A)
        epr = self.calculate_epr(data.eta_s, data.eta_r)
        is_standard_zero = epr >= self.STANDARD_ZERO_EPR
        ds_compliant = data.ds_score <= self.epsilon

        # 2. Certification status (IIAE-Certified vs IIAE-Compliant)
        # IIAE-CERTIFIED requires: audit + Standard-Zero EPR + D_s within threshold
        is_certified = data.tier_12_audit and is_standard_zero and ds_compliant

        # 3. Tier selection and economic base (Sec 2.1 + Reversion Rule)
        tier, royalty_base, base_type = self._select_tier_and_base(data)

        # 4. FRAND Constant C = 1.0% (non-degrading, applied on selected base)
        coeff_c = self.C_FACTOR
        base_royalty = royalty_base * coeff_c

        # Standard status label (Compliant vs Certified)
        status_std = "IIAE-CERTIFIED" if is_certified else "IIAE-COMPLIANT (BLACK-BOX)"

        # 5. ZIP (Universal Cascading Participation) - Sec 2.2
        # Applies only to Tier 1.2, with Standard-Zero + audit (i.e. certified) and T > C
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

        # 6. Safe Harbor status (Sec 3.1 / 3.3)
        # Only Certified implementations can access Safe Harbor; Tier 1.2 requires D_s = 0.
        if is_certified:
            if tier == "1.2 INFRASTRUCTURE":
                is_sh = (data.ds_score == 0.0)
                sh_status = "ACTIVE" if is_sh else "PENDING_DS_STABILIZATION"
                sh_reason = "CERTIFIED_DETERMINISTIC_TRUST" if is_sh else "AUDITABLE_BUT_DRIFTING"
            else:
                # Certified but non-infrastructure (edge case) → operational Safe Harbor
                is_sh = ds_compliant
                sh_status = "ACTIVE" if is_sh else "PENDING_DS_STABILIZATION"
                sh_reason = "OPERATIONALLY_COMPLIANT" if is_sh else "DRIFT_ABOVE_THRESHOLD"
        else:
            is_sh = False
            sh_status = "UNAVAILABLE (SOLE LIABILITY)"
            sh_reason = "NON_AUDITABLE_OR_LOW_INTEGRITY_BASE"

        # 7. CTM Seal (immutable audit block)
        timestamp = time.time()
        trace = data.trace_id or hashlib.sha256(str(timestamp).encode()).hexdigest()[:12]

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
            "timestamp": timestamp,
        }
        seal_payload = json.dumps(seal_block, sort_keys=True)
        ctm_seal = hashlib.sha256(seal_payload.encode()).hexdigest()

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
                # Explicit Tier 1.2 eligibility flag (Sec 2.1 Reversion Rule)
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
                "audit_ref": "WO2026/XXXXX_SLT_V3.3_ANNEX_A",
                "logic": "FIXED_C_WITH_TIER_REVERSION_AND_ZIP",
                "claims_ref": "1,19,23,8.5.1" if data.system_critical else "1,19",
                "governance": "MAII/MAO-Protocol-Compliant",
            },
        }

    def generate_certificate(self, report: Dict[str, Any]) -> str:
        """Generates human-readable certificate text for ETSI / regulatory audit."""
        sh_note = ""
        tier = report.get("tier")
        safe_harbor_status = report.get("status", {}).get("safe_harbor")

        if tier == "1.2 INFRASTRUCTURE":
            if safe_harbor_status == "ACTIVE":
                sh_note = (
                    "FULL_SAFE_HARBOR: Ds=0 verified. Eligible for Mutualized Defense Fund Sec 3.3."
                )
            elif safe_harbor_status == "PENDING_DS_STABILIZATION":
                sh_note = (
                    "QUARANTINED: Tier 1.2 requires Ds=0.00 for full Safe Harbor per Sec 5.4.2."
                )
            else:
                sh_note = "NO_SAFE_HARBOR: Infrastructure without certified deterministic integrity."
        elif safe_harbor_status == "ACTIVE":
            sh_note = (
                "OPERATIONALLY_COMPLIANT: Ds <= epsilon. Due Diligence proof for AI Act Art.15."
            )
        else:
            sh_note = "QUARANTINED: Dissonance above threshold or non-auditable. No Safe Harbor."

        return f"""

Tier Applied: {report['tier']}

TECHNICAL METRICS - ANNEX I
EPR Index: {report['metrics']['epr']} (ηS/(ηS+ηR))
Ds Score: {report['metrics']['ds_score']} (Dissonance Coefficient)
C-Factor: {report['metrics']['coeff_c']} (FRAND Constant C = 0.01)

COMPLIANCE STATUS - SEC 3.1 + 5.4.2
Standard: {report['status']['standard']}
Safe Harbor: {report['status']['safe_harbor']}
Reason: {sh_note}
Tier 1.2 Eligible: {report['status']['tier_12_eligible']}

FINANCIAL SETTLEMENT - SEC 2.1 + 2.2
Base Type: {report['metrics']['base_type']}
Base Value: ${report['metrics']['base_value']:,.2f}
Base Royalty (C): ${report['financials']['base_royalty']:,.4f}
ZIP Fund (Service Fee): ${report['financials']['zip_participation']:,.4f}
ZIP Floor Applied: {report['financials']['zip_floor_applied']}
TOTAL: ${report['financials']['total_settlement']:,.4f} USD

CRYPTOGRAPHIC PROOF - SEC 5.4.2
CTM Seal: {report['compliance']['ctm_seal']}
Audit Ref: {report['compliance']['audit_ref']}
Claims Practiced: {report['compliance']['claims_ref']}
Governance: {report['compliance']['governance']}

This certificate constitutes technical proof of Due Diligence
under EU AI Act Art.15, UNECE R155, ISO 26262 ASIL-D, DO-178C.
Verification: Hash CTM block with SHA256 to validate seal.

"""


# --- EXECUTABLE DEMO SUITE ---
if __name__ == "__main__":
    slt = SLT_StandardZero_Engine()

    print("=" * 70)
    print("DEMO 1: APPLIANCE - Tier 1.1 SSPPU Option")
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

    print("\n" + "=" * 70)
    print("DEMO 2: ELECTRIC CAR - System-Level (Sec 2.1.2)")
    print("=" * 70)
    d2 = SettlementInput(
        nsp=80_000.0,
        eta_s=99.9,
        eta_r=0.1,         # EPR ≈ 0.999 (Standard-Zero)
        ds_score=0.0,      # Ds=0 required for DO-178C / ASIL-D style profiles
        system_critical=True,
        trace_id="CAR-MODEL-SZ-001",
    )
    r2 = slt.calculate_settlement(d2)
    print(slt.generate_certificate(r2))

    print("\n" + "=" * 70)
    print("DEMO 3: COMMERCIAL AI SERVICE - Tier 1.2 with ZIP")
    print("=" * 70)
    d3 = SettlementInput(
        service_revenue=10_000_000.0,  # $10M/month Integrity-Certified Revenue
        eta_s=99.8,
        eta_r=0.2,                     # EPR ≈ 0.998 (Standard-Zero)
        ds_score=0.0,                  # Ds=0 → full Safe Harbor possible
        margin_t=0.20,                 # 20% integrity premium (T)
        tier_12_audit=True,            # Continuous CTM logs + EPR reporting
        trace_id="GEMINI-2026-05",
    )
    r3 = slt.calculate_settlement(d3)
    print(slt.generate_certificate(r3))

    print("\n" + "=" * 70)
    print("DEMO 4: SPACEX STARSHIP - Critical System (System-Level)")
    print("=" * 70)
    d4 = SettlementInput(
        nsp=100_000_000.0,  # $100M per vehicle
        eta_s=99.99,
        eta_r=0.01,         # EPR ≈ 0.9999 (Standard-Zero)
        ds_score=0.0,       # Ds=0 for mission-critical aerospace
        system_critical=True,
        trace_id="STARSHIP-SN42",
    )
    r4 = slt.calculate_settlement(d4)
    print(slt.generate_certificate(r4))

    print("\n" + "=" * 70)
    print("DEMO 5: REVERSION RULE - Tier 1.2 declared, no audit → Tier 1.1")
    print("=" * 70)
    d5 = SettlementInput(
        service_revenue=5_000_000.0,   # Intended Integrity Revenue
        nsp=50_000_000.0,              # NSP used for reversion
        eta_s=99.5,
        eta_r=0.5,
        ds_score=0.0,
        tier_12_audit=False,           # No CTM logs → automatic reversion to Tier 1.1
        trace_id="AI-SERVICE-NO-AUDIT",
    )
    r5 = slt.calculate_settlement(d5)
    print(slt.generate_certificate(r5))
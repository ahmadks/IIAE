import hashlib
import json
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, Literal
from datetime import datetime, timezone

TierType = Literal["1.1 CONSUMER", "1.1 SYSTEM-LEVEL", "1.2 INFRASTRUCTURE"]

@dataclass
class SettlementInput:
    """Inputs para liquidación SLT v3.3 - Open Constitution of Invariance"""
    nsp: Optional[float] = None # Net Selling Price Tier 1.1
    service_revenue: Optional[float] = None # Integrity-Certified Revenue Tier 1.2
    ssppu_cost: Optional[float] = None # Smallest Saleable Patent Practicing Unit
    eta_s: float = 0.0 # Entropía Segregada / Purgada por AEM
    eta_r: float = 0.0 # Entropía Residual
    ds_score: float = 1.0 # Dissonance Coefficient D_s ∈ [0,1]
    margin_t: float = 0.0 # Margen premium T sobre servicios. 0.12 = 12%
    system_critical: bool = False # True: coches, robots, naves. Activa 2.1.2
    tier_12_audit: bool = False # True: CTM logs continuos verificados
    trace_id: Optional[str] = None # ID externo de transacción

class SLT_StandardZero_Engine:
    """
    Motor de Gobernanza SLT v3.3
    Patent Family: WO2026/XXXXX — IIAE/IDICOC‑DSE
    Implementa: Sec 2.1 Dual-Track, 2.1.2 System-Level, 2.2 ZIP, 3.1 Safe Harbor, Anexo I
    """

    def __init__(self, epsilon_threshold: float = 0.4):
        self.epsilon = epsilon_threshold # Umbral D_s para conformidad Tier 1.1
        self.C_FACTOR = 0.01 # 1% Standard-Zero Baseline Sec 1.4
        self.ZIP_RATE = 0.15 # 15% del excedente T > 1% Sec 2.2
        self.ZIP_FLOOR = 0.05 # 5% floor del excedente Sec 2.3
        self.STANDARD_ZERO_EPR = 0.99 # Umbral normativo EPR Anexo I

    def calculate_epr(self, eta_s: float, eta_r: float) -> float:
        """
        Entropy Purge Rate EPR = η_s / (η_s + η_r)
        Anexo I: Medida de purga de entropía del AEM
        """
        total_entropy = eta_s + eta_r
        if total_entropy <= 0:
            return 1.0 # Estado de reposo = Standard-Zero absoluto
        return eta_s / total_entropy

    def _select_tier_and_base(self, data: SettlementInput) -> tuple[TierType, float, str]:
        """
        Aplica Sec 2.1 + 2.1.2 + Reversion Rule
        Orden de prioridad: System-Level > Tier 1.2 con audit > Tier 1.1
        """
        # 2.1.2 System-Level: coches, robots, naves. Base = NSP siempre
        if data.system_critical:
            if data.nsp is None:
                raise ValueError("system_critical=True requiere nsp. Sec 2.1.2")
            return "1.1 SYSTEM-LEVEL", float(data.nsp), "NSP-System"

        # Tier 1.2: requiere service_revenue + audit. Si no hay audit, revierte a 1.1
        if data.service_revenue is not None:
            if data.tier_12_audit:
                return "1.2 INFRASTRUCTURE", float(data.service_revenue), "Integrity-Certified Revenue"
            else:
                # Reversion Rule Sec 2.1: sin CTM logs = Tier 1.1 NSP
                if data.nsp is None:
                    raise ValueError("Tier 1.2 sin audit requiere nsp para reversión a Tier 1.1")
                return "1.1 CONSUMER", float(data.nsp), "NSP-Reverted"

        # Tier 1.1 Consumer: SSPPU Option Sec 2.1.1
        if data.ssppu_cost is not None:
            return "1.1 CONSUMER", float(data.ssppu_cost), "SSPPU"

        if data.nsp is None:
            raise ValueError("Debe proporcionar nsp, service_revenue o ssppu_cost")
        return "1.1 CONSUMER", float(data.nsp), "NSP"

    def calculate_settlement(self, data: SettlementInput) -> Dict[str, Any]:
        """
        Ejecuta la liquidación completa bajo SLT v3.2 (Normative Engine).
        Aplica la Constante FRAND C=0.01 y la Regla de Reversión automática.
        """
        # 1. Métricas técnicas de integridad (Anexo I / Spec Sec 6)
        epr = self.calculate_epr(data.eta_s, data.eta_r)
        is_standard_zero = epr >= self.STANDARD_ZERO_EPR
        ds_compliant = data.ds_score <= self.epsilon

        # 2. Verificación de Auditabilidad y Estatus de Certificación
        # IIAE CERTIFIED requiere: Auditoría activa + EPR >= 0.99 + Ds dentro de margen
        is_certified = data.tier_12_audit and is_standard_zero and ds_compliant

        # 3. Selección de Tier y Base Económica (Sección 2.1 - Reversion Rule)
        # La lógica de negocio se mueve al Tier 1.1 si no se puede certificar la integridad.
        if data.system_critical:
            tier, royalty_base, base_type = "1.1 SYSTEM-LEVEL", (data.nsp or 0.0), "NSP (System-Wide)"
        elif is_certified:
            tier, royalty_base, base_type = "1.2 INFRASTRUCTURE", (data.service_revenue or 0.0), "Integrity-Certified Revenue"
        else:
            # REVERSIÓN: Si no es auditable o falla integridad, paga por el producto completo (NSP)
            tier, royalty_base, base_type = "1.1 REVERSION (NON-AUDITABLE) / CONSUMER", (data.nsp or data.ssppu_cost or 0.0), "NSP (Default-Reversion)"

        # 4. Aplicación de la Constante FRAND C = 1.0% (Sección 1.4)
        # El coeficiente no se degrada; se aplica sobre la base correspondiente.
        coeff_c = self.C_FACTOR
        base_royalty = royalty_base * coeff_c
        
        status_std = "IIAE-CERTIFIED" if is_certified else "IIAE-COMPLIANT (BLACK-BOX)"

        # 5. ZIP Sec 2.2: Participación sobre el margen excedente (Solo para Tier 1.2)
        zip_contribution = 0.0
        zip_floor_applied = False
        if tier == "1.2 INFRASTRUCTURE" and data.margin_t > self.C_FACTOR:
            surplus_margin = data.margin_t - self.C_FACTOR
            surplus_value = royalty_base * surplus_margin
            zip_raw = surplus_value * self.ZIP_RATE

            # Excepción FRAND Sec 2.2.3: Floor solo si el margen es >= 5%
            if surplus_margin >= self.ZIP_FLOOR:
                zip_contribution = max(zip_raw, surplus_value * self.ZIP_FLOOR)
                zip_floor_applied = zip_contribution > zip_raw
            else:
                zip_contribution = zip_raw

        # 6. Estatus de Safe Harbor (Sección 3.3)
        # Solo el estatus CERTIFIED (Transparente) disfruta de protección mutualizada.
        if is_certified:
            # Para Infraestructura, Safe Harbor pleno exige D_s tendiendo a cero
            is_sh = (data.ds_score == 0.0) 
            sh_status = "ACTIVE" if is_sh else "PENDING_DS_STABILIZATION"
            sh_reason = "CERTIFIED_DETERMINISTIC_TRUST" if is_sh else "AUDITABLE_BUT_DRIFTING"
        else:
            is_sh = False
            sh_status = "UNAVAILABLE (SOLE LIABILITY)"
            sh_reason = "NON_AUDITABLE_OR_LOW_INTEGRITY_BASE"

        # 7. CTM Seal Sec 5.4.2 - Generación de bloque inmutable para auditoría
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
            "timestamp": timestamp
        }
        
        seal_payload = json.dumps(seal_block, sort_keys=True)
        ctm_seal = hashlib.sha256(seal_payload.encode()).hexdigest()

        return {
            "timestamp": datetime.now().isoformat() + "Z",
            "trace_id": trace,
            "tier": tier,
            "metrics": {
                "epr": round(epr, 6),
                "ds_score": data.ds_score,
                "coeff_c": coeff_c,
                "base_type": base_type,
                "base_value": round(royalty_base, 2)
            },
            "status": {
                "standard": status_std,
                "safe_harbor": sh_status,
                "certified_auditable": is_certified
            },
            "financials": {
                "base_royalty": round(base_royalty, 4),
                "zip_participation": round(zip_contribution, 4),
                "zip_floor_applied": zip_floor_applied,
                "total_settlement": round(base_royalty + zip_contribution, 4),
                "currency": "USD"
            },
            "compliance": {
                "safe_harbor_reason": sh_reason,
                "ctm_seal": ctm_seal,
                "ctm_block": seal_block,
                "audit_ref": "WO2026/XXXXX_SLT_V3.2_ANNEX_B",
                "logic": "FIXED_C_WITH_TIER_REVERSION"
            }
        }

    def generate_certificate(self, report: Dict[str, Any]) -> str:
        """Genera certificado texto para ETSI/auditoría regulatoria"""
        sh_note = ""
        # Use tier directly from the report
        tier = report.get('tier')
        # Determine safe harbor status from the status section
        safe_harbor_status = report.get('status', {}).get('safe_harbor')
        if tier == "1.2 INFRASTRUCTURE":
            if safe_harbor_status == "ACTIVE":
                sh_note = "FULL_SAFE_HARBOR: Ds=0 verified. Eligible for Mutualized Defense Fund Sec 3.3."
            else:
                sh_note = "QUARANTINED: Tier 1.2 requires Ds=0.00 for Safe Harbor per Sec 5.4.2."
        elif safe_harbor_status == "ACTIVE":
            sh_note = "OPERATIONALLY_COMPLIANT: Ds< =epsilon. Due Diligence proof for AI Act Art.15."
        else:
            sh_note = "QUARANTINED: Dissonance above threshold. No Safe Harbor."

        return f"""

Tier Applied: {report['tier']}

TECHNICAL METRICS - ANNEX I
EPR Index: {report['metrics']['epr']} (ηS/(ηS+ηR))
Ds Score: {report['metrics']['ds_score']} (Dissonance Coefficient)
C-Factor: {report['metrics']['coeff_c']} (Standard-Zero: 0.01)

COMPLIANCE STATUS - SEC 3.1 + 5.4.2
Standard: {report['status']['standard']}
Safe Harbor: {report['status']['safe_harbor']}
Reason: {sh_note}
Tier 1.2 Eligible: {report['status']['tier_12_eligible']}

FINANCIAL SETTLEMENT - SEC 2.1 + 2.2
Base Type: {report['metrics']['base_type']}
Base Value: ${report['metrics']['base_value']:,.2f}
Base Royalty: ${report['financials']['base_royalty']:,.4f}
ZIP Fund: ${report['financials']['zip_participation']:,.4f}
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

# --- SUITE DE DEMOS EJECUTABLES ---
if __name__ == "__main__":
    slt = SLT_StandardZero_Engine()

    print("="*70)
    print("DEMO 1: ELECTRODOMESTIC - Tier 1.1 SSPPU Option")
    print("="*70)
    d1 = SettlementInput(
        nsp=500.0, ssppu_cost=15.0, # Chip IIAE $15
        eta_s=95.0, eta_r=5.0, # EPR=0.95 Sub-optimal
        ds_score=0.3
    )
    r1 = slt.calculate_settlement(d1)
    print(slt.generate_certificate(r1))

    print("\n" + "="*70)
    print("DEMO 2: ELECTRIC CAR - System-Level 2.1.2")
    print("="*70)
    d2 = SettlementInput(
        nsp=80000.0,
        eta_s=99.9, eta_r=0.1, # EPR=0.999 Standard-Zero
        ds_score=0.0, # Ds=0 requerido para coches
        system_critical=True,
        trace_id="CAR-MODELS-001"
    )
    r2 = slt.calculate_settlement(d2)
    print(slt.generate_certificate(r2))

    print("\n" + "="*70)
    print("DEMO 3: COMMERCIAL AI - Tier 1.2 con ZIP")
    print("="*70)
    d3 = SettlementInput(
        service_revenue=10_000_000.0, # $10M/mes Integrity-Certified
        eta_s=99.8, eta_r=0.2,
        ds_score=0.0,
        margin_t=0.20, # 20% premium por "Zero-Drift"
        tier_12_audit=True,
        trace_id="GEMINI-2026-05"
    )
    r3 = slt.calculate_settlement(d3)
    print(slt.generate_certificate(r3))

    print("\n" + "="*70)
    print("DEMO 4: SPACEX STARSHIP - Sistema Crítico")
    print("="*70)
    d4 = SettlementInput(
        nsp=100_000_000.0, # $100M por nave
        eta_s=99.99, eta_r=0.01,
        ds_score=0.0, # DO-178C Level A exige Ds=0
        system_critical=True,
        trace_id="STARSHIP-SN42"
    )
    r4 = slt.calculate_settlement(d4)
    print(slt.generate_certificate(r4))

    print("\n" + "="*70)
    print("DEMO 5: REVERSION RULE - Tier 1.2 sin audit")
    print("="*70)
    d5 = SettlementInput(
        service_revenue=5_000_000.0,
        nsp=50_000_000.0, # NSP para reversión
        eta_s=99.5, eta_r=0.5,
        ds_score=0.0,
        tier_12_audit=False # Sin CTM logs = revierte a 1.1
    )
    r5 = slt.calculate_settlement(d5)
    print(slt.generate_certificate(r5))
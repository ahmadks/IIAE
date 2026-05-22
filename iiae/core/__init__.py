"""
IIAE Core Module

Stable public API for integrity verification.
"""

from .errors import CircuitBreakerError, IntegrityError
from .receipts import create_receipt, verify_receipt
from .audit import build_audit_record, log_audit_record, verify_audit_chain
from .dse import DynamicSchemaExtractor, PropertyGraph
from .isg import CanonicalState, InvariantStateGenerator

__all__ = [
    "IntegrityError",
    "CircuitBreakerError",
    "create_receipt",
    "verify_receipt",
    "build_audit_record",
    "log_audit_record",
    "verify_audit_chain",
    "DynamicSchemaExtractor",
    "PropertyGraph",
    "CanonicalState",
    "InvariantStateGenerator",
]

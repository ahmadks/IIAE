"""
IIAE Core Exceptions

Standard exception types for IIAE integrity verification.
"""


class IntegrityError(Exception):
    """
    Raised when integrity verification fails.

    Indicates that AI response violates structural/policy constraints
    and has been rejected by IIAE.
    """
    pass


class CircuitBreakerError(Exception):
    """
    Raised when circuit breaker is open.

    Indicates system has experienced too many failures and is in
    fail-closed mode. Retry later.
    """
    pass

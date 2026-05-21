"""
iiae.mao — Material Axiomatic Ontology (Technical Annex V).

Pluggable forensic filters; integrate any LLM/ML engine via ``IMAOEngine``.
"""

from .contract import IMAOEngine, MAOReport
from .lexical import LexicalMAOEngine
from .registry import register_engine, get_engine, list_registered_engines
from .composite import CompositeMAOEngine
from .auditor import MAOAuditor, compare_reports
from .filters import MAOFilterConfig
from .report import enrich_report

register_engine("composite", CompositeMAOEngine)

__all__ = [
    "IMAOEngine",
    "MAOReport",
    "MAOFilterConfig",
    "enrich_report",
    "MAOAuditor",
    "compare_reports",
    "register_engine",
    "get_engine",
    "list_registered_engines",
    "LexicalMAOEngine",
    "CompositeMAOEngine",
]

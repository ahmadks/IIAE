"""Helpers for MAO filter reports (enterprise traceability)."""

from typing import Any, Dict


def enrich_report(report: dict, **metadata: Any) -> Dict[str, Any]:
    """Attach or merge a ``metadata`` block into a filter report."""
    result = dict(report)
    meta = dict(result.get("metadata") or {})
    meta.update(metadata)
    result["metadata"] = meta
    return result

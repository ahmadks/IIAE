"""
IIAE Pipeline Debug Module

Full 7-stage IDICOC pipeline for auditors and certification bodies.
NOT for production — use iiae.validate() for that.
"""

from .debug_pipeline import run_debug_pipeline, print_debug_trace
from .aem import decompose_response, measure_entropy_purge_rate
from .isg import canonicalize_state, is_stable_fixed_point
from .cmc import construct_manifold_boundary, is_point_on_manifold, project_to_manifold

__all__ = [
    "run_debug_pipeline",
    "print_debug_trace",
    "decompose_response",
    "measure_entropy_purge_rate",
    "canonicalize_state",
    "is_stable_fixed_point",
    "construct_manifold_boundary",
    "is_point_on_manifold",
    "project_to_manifold",
]

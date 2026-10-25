"""Scheduler graph export helpers.

This module must not import NetworkX at module import time.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from .types import GraphAnalysisSummary


def graph_summary_to_dict(summary: GraphAnalysisSummary) -> Dict[str, Any]:
    return {
        "node_count": summary.node_count,
        "edge_count": summary.edge_count,
        "is_dag": summary.is_dag,
        "cycle_edges": list(summary.cycle_edges),
        "topological_order": list(summary.topological_order),
        "critical_path": list(summary.critical_path),
        "critical_path_minutes": summary.critical_path_minutes,
        "node_metrics": dict(summary.node_metrics),
        "warnings": [asdict(warning) for warning in summary.warnings],
    }


__all__ = ["graph_summary_to_dict"]

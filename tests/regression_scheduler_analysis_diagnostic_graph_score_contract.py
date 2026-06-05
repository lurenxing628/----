from __future__ import annotations

from typing import Any, Iterable

from web.viewmodels.scheduler_analysis_diagnostics import build_diagnostic_sections


def _iter_text(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _iter_text(child)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_text(item)
    elif value is not None:
        yield str(value)


def test_graph_score_sample_does_not_expose_internal_operation_id() -> None:
    sections = build_diagnostic_sections(
        {
            "algo": {
                "graph_analysis": {
                    "status": "available",
                    "is_dag": True,
                    "node_count": 1,
                    "edge_count": 0,
                    "critical_path_minutes": 0,
                    "critical_path_node_count": 0,
                    "warning_count": 0,
                    "cycle_edge_count": 0,
                    "time_cost_ms": 1,
                },
                "metrics": {"overdue_count": 0, "total_tardiness_hours": 0},
            },
            "diagnostics": {
                "graph_analysis": {
                    "graph_score_sample": [
                        {
                            "op_id": 1,
                            "impact_count": 3,
                            "downstream_critical_minutes": 180,
                            "bonus": 530,
                            "priority_key": [-530.0, 0.0],
                        }
                    ]
                }
            },
        },
        selected_ver=7,
    )

    text_blob = "\n".join(_iter_text(sections))
    assert "重点影响样本（影响 3 个后续，后续关键时长 180 分钟，排法参考值 530）" in text_blob
    assert "工序 1" not in text_blob
    assert "op_id" not in text_blob
    assert "priority_key" not in text_blob

"""语义 snapshot —— 锁住对外语义 I/O 形状(default/choices/中文标签)。

首次运行用 APS_UPDATE_SEMANTIC_SNAPSHOTS=1 建立基线；之后任何漂移即红灯。
锁的是“公开小契约”，不锁完整算法输出。
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "tools"))

from snapshot_json import assert_json_snapshot  # noqa: E402

from core.models import schedule_plan_role as pr  # noqa: E402
from core.services.scheduler.config import config_field_spec as cfs  # noqa: E402

_SNAP = _HERE / "__snapshots__"

_GRAPH_KEYS = (
    "graph_analysis_mode",
    "graph_block_on_cycle",
    "graph_critical_weight",
    "graph_impact_weight",
    "graph_candidate_weight_count",
    "graph_selection_policy",
    "graph_overdue_tolerance_count",
    "graph_tardiness_tolerance_ratio",
)


def test_plan_role_labels_snapshot():
    assert_json_snapshot(dict(pr.PLAN_ROLE_LABELS), str(_SNAP / "plan_role_labels.json"))


def test_result_status_labels_snapshot():
    from web.viewmodels.scheduler_summary_result_state import result_status_display_labels

    assert_json_snapshot(result_status_display_labels(), str(_SNAP / "result_status_labels.json"))


def test_strategy_labels_snapshot():
    from web.viewmodels.scheduler_history_summary import _STRATEGY_LABELS

    assert_json_snapshot(dict(_STRATEGY_LABELS), str(_SNAP / "strategy_labels.json"))


def test_graph_config_defaults_snapshot():
    actual = {}
    for key in _GRAPH_KEYS:
        if not cfs.has_config_field(key):
            continue
        spec = cfs.get_field_spec(key)
        actual[key] = {
            "field_type": spec.field_type,
            "default": spec.default,
            "choices": list(spec.choices),
            "label": spec.label,
            "page_label": spec.page_metadata.label if spec.page_metadata else "",
        }
    assert_json_snapshot(actual, str(_SNAP / "graph_config_defaults.json"))

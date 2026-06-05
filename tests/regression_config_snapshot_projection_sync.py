"""回归测试：守护 ScheduleConfigSnapshot 与字段注册表三方对齐——快照投影键、默认值键、build_schedule_config_snapshot 输出键必须与 list_config_fields 一致；config_snapshot 源文件不得重复声明字段；strict 模式拒绝权重三元组不一致与非法 ready_weight；并保留模型运行期降级事件/计数器。"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.config.config_field_spec import default_snapshot_values, list_config_fields
from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot
from core.services.scheduler.config.config_validator import normalize_preset_snapshot
from core.services.scheduler.config_snapshot import ScheduleConfigSnapshot, build_schedule_config_snapshot

REPO_ROOT = Path(__file__).resolve().parents[1]


class _EmptyRepo:
    def get_value(self, key, default=None):
        return default


class _ValueRepo:
    def __init__(self, values):
        self._values = dict(values or {})

    def get_value(self, key, default=None):
        return self._values.get(key, default)


def _make_snapshot(**overrides) -> ScheduleConfigSnapshot:
    values = {
        "sort_strategy": "priority_first",
        "priority_weight": 0.4,
        "due_weight": 0.5,
        "ready_weight": 0.1,
        "holiday_default_efficiency": 0.8,
        "enforce_ready_default": "no",
        "prefer_primary_skill": "no",
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "auto_assign_enabled": "no",
        "auto_assign_persist": "yes",
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 5,
        "algo_mode": "greedy",
        "time_budget_seconds": 20,
        "objective": "min_overdue",
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
        "graph_analysis_mode": "off",
        "graph_block_on_cycle": "no",
        "graph_critical_weight": 500,
        "graph_impact_weight": 10,
        "graph_debug_export": "no",
    }
    values.update(overrides)
    return ScheduleConfigSnapshot(**values)


def test_registry_keys_match_snapshot_projection_keys() -> None:
    registry_keys = [spec.key for spec in list_config_fields()]
    default_keys = list(default_snapshot_values().keys())
    snapshot_keys = list(_make_snapshot().to_dict().keys())
    built_snapshot_keys = list(build_schedule_config_snapshot(_EmptyRepo()).to_dict().keys())

    assert snapshot_keys == registry_keys
    assert default_keys == registry_keys
    assert built_snapshot_keys == registry_keys


def _duplicate_class_annotations(path: Path, class_name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        seen = {}
        duplicates = []
        for item in node.body:
            if not isinstance(item, ast.AnnAssign) or not isinstance(item.target, ast.Name):
                continue
            field_name = item.target.id
            seen[field_name] = seen.get(field_name, 0) + 1
            if seen[field_name] == 2:
                duplicates.append(field_name)
        return duplicates
    raise AssertionError(f"{path} 缺少 {class_name}")


def test_schedule_config_snapshot_sources_do_not_duplicate_field_annotations() -> None:
    targets = [
        REPO_ROOT / "core" / "services" / "scheduler" / "config" / "config_snapshot.py",
        REPO_ROOT / "core" / "models" / "schedule_config_runtime_snapshot.py",
    ]
    failures = []

    for path in targets:
        duplicates = _duplicate_class_annotations(path, "ScheduleConfigSnapshot")
        if duplicates:
            failures.append(f"{path.relative_to(REPO_ROOT)}: {', '.join(duplicates)}")

    assert not failures, "ScheduleConfigSnapshot 存在重复字段声明: " + "; ".join(failures)


def test_strict_snapshot_rejects_inconsistent_weight_triplet() -> None:
    payload = _make_snapshot(priority_weight=0.4, due_weight=0.5, ready_weight=0.9).to_dict()

    with pytest.raises(ValidationError) as build_exc:
        build_schedule_config_snapshot(_ValueRepo(payload), strict_mode=True)
    with pytest.raises(ValidationError) as ensure_exc:
        ensure_schedule_config_snapshot(payload, strict_mode=True)

    assert build_exc.value.field == "权重"
    assert ensure_exc.value.field == "权重"


def test_strict_preset_normalization_rejects_invalid_or_mismatched_ready_weight() -> None:
    base = _make_snapshot()
    invalid_ready = base.to_dict()
    invalid_ready["ready_weight"] = "abc"
    mismatched_ready = base.to_dict()
    mismatched_ready["ready_weight"] = 0.9

    with pytest.raises(ValidationError) as invalid_exc:
        normalize_preset_snapshot(invalid_ready, base=base, strict_mode=True)
    with pytest.raises(ValidationError) as mismatch_exc:
        normalize_preset_snapshot(mismatched_ready, base=base, strict_mode=True)

    assert invalid_exc.value.field == "ready_weight"
    assert mismatch_exc.value.field == "权重"


def test_service_snapshot_preserves_model_runtime_degradation_events() -> None:
    from core.models.schedule_config_runtime import ScheduleConfigSnapshot as RuntimeScheduleConfigSnapshot

    event = {
        "code": "invalid_choice",
        "scope": "scheduler.runtime_config",
        "field": "dispatch_mode",
        "message": "字段“dispatch_mode”取值不正确，本次先按默认值处理。",
        "count": 2,
        "sample": "'bad'",
    }
    runtime_snapshot = RuntimeScheduleConfigSnapshot(
        **_make_snapshot(
            degradation_events=(event,),
            degradation_counters={"invalid_choice": 2},
        ).__dict__
    )

    normalized = ensure_schedule_config_snapshot(runtime_snapshot, strict_mode=False)

    assert normalized.degradation_events == (event,)
    assert normalized.degradation_counters == {"invalid_choice": 2}

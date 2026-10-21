from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, cast

from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot, snapshot_from_values
from core.models.schedule_config_runtime_weights import normalize_weight_triplet
from core.shared.degradation import (
    DegradationCollector,
    degradation_events_to_dicts,
)

from .config_field_spec import (
    MISSING_POLICY_ERROR,
    MISSING_POLICY_FALLBACK_WITH_DEGRADATION,
    coerce_config_field,
    default_snapshot_values,
    list_config_fields,
)


def build_schedule_config_snapshot(
    repo,
    *,
    defaults: Optional[Dict[str, Any]] = None,
    strict_mode: bool = False,
    rows: Optional[List[Any]] = None,
) -> ScheduleConfigSnapshot:
    collector = DegradationCollector()
    raw_missing = object()
    default_map = default_snapshot_values()
    if isinstance(defaults, dict):
        default_map.update(defaults)
    by_key = None if rows is None else {
        str(row.get("config_key") if isinstance(row, dict) else row.config_key): row for row in rows
    }

    def _raise_repo_get_contract_error(key: str, record: Any) -> None:
        raise TypeError(
            f"repo.get({key}) 返回值必须为包含 config_value 的 dict，或具备 config_value 属性的记录对象"
            f"（实际={type(record).__name__}）。"
        )

    def _read_repo_raw_value(key: str) -> Tuple[bool, Any]:
        repo_get = getattr(repo, "get", None)
        if by_key is not None or callable(repo_get):
            record = by_key.get(key) if by_key is not None else cast(Callable[[str], Any], repo_get)(key)
            if record is None:
                return True, None
            if isinstance(record, dict):
                if "config_value" in record:
                    return False, record.get("config_value")
                _raise_repo_get_contract_error(key, record)
            config_value = getattr(record, "config_value", raw_missing)
            if config_value is not raw_missing:
                return False, config_value
            _raise_repo_get_contract_error(key, record)

        raw = repo.get_value(key, default=raw_missing)
        if raw is raw_missing:
            return True, None
        return False, raw

    values: Dict[str, Any] = {}
    if bool(strict_mode):
        for spec in list_config_fields():
            missing, raw = _read_repo_raw_value(spec.key)
            if missing:
                continue
            values[spec.key] = coerce_config_field(
                spec.key,
                raw,
                strict_mode=True,
                source="scheduler.config_snapshot",
                collector=collector,
                missing=False,
                fallback=default_map[spec.key],
                missing_policy=MISSING_POLICY_ERROR,
            )

    for spec in list_config_fields():
        if bool(strict_mode) and spec.key in values:
            continue
        missing, raw = (True, None) if bool(strict_mode) else _read_repo_raw_value(spec.key)
        values[spec.key] = coerce_config_field(
            spec.key,
            raw,
            strict_mode=bool(strict_mode),
            source="scheduler.config_snapshot",
            collector=collector,
            missing=missing,
            fallback=default_map[spec.key],
            missing_policy=(MISSING_POLICY_ERROR if bool(strict_mode) else MISSING_POLICY_FALLBACK_WITH_DEGRADATION),
        )
    if bool(strict_mode):
        values["priority_weight"], values["due_weight"], values["ready_weight"] = normalize_weight_triplet(
            values["priority_weight"],
            values["due_weight"],
            values["ready_weight"],
            require_sum_1=True,
            priority_field="优先级权重",
            due_field="交期权重",
            ready_field="齐套权重",
        )

    return snapshot_from_values(
        values, degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),
        degradation_counters=collector.to_counters(),
    )

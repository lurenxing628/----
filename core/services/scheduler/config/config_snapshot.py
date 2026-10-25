from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from core.models.schedule_config_runtime_fields import default_snapshot_values
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot, snapshot_from_values
from core.models.schedule_config_runtime_weights import normalize_weight_triplet
from core.shared.degradation import (
    DegradationCollector,
    degradation_events_to_dicts,
)

from .config_field_spec import (
    MISSING_POLICY_ERROR,
    coerce_config_field,
    list_config_fields,
)


def build_schedule_config_snapshot(*, rows: Iterable[Mapping[str, Any]]) -> ScheduleConfigSnapshot:
    collector = DegradationCollector()
    default_map = default_snapshot_values()
    by_key = {row["config_key"]: row["config_value"] for row in rows}

    values: Dict[str, Any] = {}
    for spec in list_config_fields():
        missing = spec.key not in by_key
        values[spec.key] = coerce_config_field(
            spec.key,
            None if missing else by_key[spec.key],
            strict_mode=True,
            source="scheduler.config_snapshot",
            collector=collector,
            missing=missing,
            fallback=default_map[spec.key],
            missing_policy=MISSING_POLICY_ERROR,
        )
    values["priority_weight"], values["due_weight"], values["ready_weight"] = normalize_weight_triplet(
        values["priority_weight"],
        values["due_weight"],
        values["ready_weight"],
    )

    return snapshot_from_values(
        values,
        degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),
        degradation_counters=collector.to_counters(),
    )

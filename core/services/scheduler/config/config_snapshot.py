from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot, snapshot_from_values
from core.models.schedule_config_runtime_weights import normalize_weight_triplet

from .config_field_spec import coerce_config_field, list_config_fields


def build_schedule_config_snapshot(*, rows: Iterable[Mapping[str, Any]]) -> ScheduleConfigSnapshot:
    """The only production snapshot source: strict, and a missing or invalid row is an error."""
    by_key = {row["config_key"]: row["config_value"] for row in rows}

    values: Dict[str, Any] = {}
    for spec in list_config_fields():
        missing = spec.key not in by_key
        values[spec.key] = coerce_config_field(spec.key, None if missing else by_key[spec.key], missing=missing)
    values["priority_weight"], values["due_weight"], values["ready_weight"] = normalize_weight_triplet(
        values["priority_weight"],
        values["due_weight"],
        values["ready_weight"],
    )

    return snapshot_from_values(values)

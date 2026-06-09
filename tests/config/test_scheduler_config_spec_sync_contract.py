"""回归测试：排产配置的两套字段规格须始终同步——config_field_spec.list_config_fields() 与 schedule_config_runtime.list_runtime_config_fields() 的 key 集合、field_type/default/min_value/min_inclusive/choices 必须逐项一致，且九个 graph_* 配置字段在两套规格中均按既定契约注册。"""

from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from core.models import schedule_config_runtime_coercion as runtime_coercion
from core.models import schedule_config_runtime_read as runtime_read
from core.models.schedule_config_runtime import list_runtime_config_fields
from core.models.schedule_config_runtime_coercion import (
    coerce_runtime_config_field,
)
from core.models.schedule_config_runtime_coercion import (
    ensure_schedule_config_snapshot as ensure_runtime_schedule_config_snapshot,
)
from core.models.schedule_config_runtime_weights import normalize_weight_triplet as normalize_runtime_weight_triplet
from core.services.scheduler.config import config_field_coercion as service_coercion
from core.services.scheduler.config import config_snapshot as service_snapshot
from core.services.scheduler.config.config_field_spec import (
    MISSING_POLICY_INHERIT_LEGACY_OMISSION,
    coerce_config_field,
    default_snapshot_values,
    list_config_fields,
)
from core.services.scheduler.config.config_snapshot import (
    ensure_schedule_config_snapshot as ensure_service_schedule_config_snapshot,
)
from core.services.scheduler.config.config_weight_policy import (
    normalize_weight_triplet as normalize_service_weight_triplet,
)
from core.shared.degradation import DegradationCollector, DegradationEvent


def test_scheduler_config_spec_and_runtime_spec_stay_in_sync() -> None:
    service_specs = {spec.key: spec for spec in list_config_fields()}
    runtime_specs = {spec.key: spec for spec in list_runtime_config_fields()}

    assert list(runtime_specs) == list(service_specs)
    for key, service_spec in service_specs.items():
        runtime_spec = runtime_specs[key]
        assert runtime_spec.field_type == service_spec.field_type
        assert runtime_spec.default == service_spec.default
        assert runtime_spec.min_value == service_spec.min_value
        assert runtime_spec.min_inclusive == service_spec.min_inclusive
        assert runtime_spec.choices == service_spec.choices


def test_graph_config_fields_are_registered_in_both_specs() -> None:
    runtime_specs = {spec.key: spec for spec in list_runtime_config_fields()}
    service_specs = {spec.key: spec for spec in list_config_fields()}

    expected = {
        "graph_analysis_mode": ("enum", "on", None, True, ("off", "report", "on")),
        "graph_block_on_cycle": ("yes_no", "no", None, True, ("yes", "no")),
        "graph_critical_weight": ("int", 500, 0, True, ()),
        "graph_impact_weight": ("int", 10, 0, True, ()),
        "graph_candidate_weight_count": ("int", 5, None, True, ("3", "5", "7")),
        "graph_selection_policy": ("enum", "balanced", None, True, ("balanced", "score_only")),
        "graph_overdue_tolerance_count": ("int", 1, None, True, ("0", "1", "2")),
        "graph_tardiness_tolerance_ratio": ("float", 0.10, None, True, ("0.05", "0.1", "0.2")),
        "graph_debug_export": ("yes_no", "no", None, True, ("yes", "no")),
    }
    for key, contract in expected.items():
        assert key in service_specs
        assert key in runtime_specs
        for specs in (service_specs, runtime_specs):
            spec = specs[key]
            assert (
                spec.field_type,
                spec.default,
                spec.min_value,
                spec.min_inclusive,
                spec.choices,
            ) == contract


def _config_payload(**overrides):
    payload = default_snapshot_values()
    payload.update(overrides)
    return payload


def _snapshot_public_values(snapshot):
    data = snapshot.to_dict()
    data["graph_downstream_weight"] = int(snapshot.graph_downstream_weight)
    return data


def _weight_outcome(func, values):
    try:
        return (
            "ok",
            func(
                values[0],
                values[1],
                values[2],
                priority_field="priority_weight",
                due_field="due_weight",
                ready_field="ready_weight",
            ),
        )
    except ValidationError as exc:
        return "error", exc.field


def test_scheduler_config_snapshot_helpers_stay_in_sync_for_good_and_degraded_values() -> None:
    good = _config_payload(graph_critical_weight=0, graph_impact_weight=0)
    service_good = ensure_service_schedule_config_snapshot(good, strict_mode=False)
    runtime_good = ensure_runtime_schedule_config_snapshot(good, strict_mode=False)

    assert _snapshot_public_values(service_good) == _snapshot_public_values(runtime_good)
    assert service_good.graph_downstream_weight == 0
    assert runtime_good.graph_downstream_weight == 0

    degraded = _config_payload(graph_analysis_mode="bad-mode")
    service_degraded = ensure_service_schedule_config_snapshot(degraded, strict_mode=False)
    runtime_degraded = ensure_runtime_schedule_config_snapshot(degraded, strict_mode=False)

    assert service_degraded.graph_analysis_mode == "on"
    assert runtime_degraded.graph_analysis_mode == "on"
    assert any(event.get("field") == "graph_analysis_mode" for event in service_degraded.degradation_events)
    assert any(event.get("field") == "graph_analysis_mode" for event in runtime_degraded.degradation_events)

    # blank 路两栈事件逐字段等价——R47 删死参 raw_value 后,blank_required 消息/回退值的单边漂移由此钉住。
    blank = _config_payload(graph_analysis_mode="")
    service_blank = ensure_service_schedule_config_snapshot(blank, strict_mode=False)
    runtime_blank = ensure_runtime_schedule_config_snapshot(blank, strict_mode=False)

    assert service_blank.graph_analysis_mode == runtime_blank.graph_analysis_mode
    service_blank_events = [e for e in service_blank.degradation_events if e.get("field") == "graph_analysis_mode"]
    runtime_blank_events = [e for e in runtime_blank.degradation_events if e.get("field") == "graph_analysis_mode"]
    assert service_blank_events and service_blank_events == runtime_blank_events
    assert service_blank_events[0].get("code") == "blank_required"


def test_scheduler_config_snapshot_strict_missing_field_matches_between_stacks() -> None:
    with pytest.raises(ValidationError) as service_exc:
        ensure_service_schedule_config_snapshot({}, strict_mode=True)
    with pytest.raises(ValidationError) as runtime_exc:
        ensure_runtime_schedule_config_snapshot({}, strict_mode=True)

    assert service_exc.value.field == runtime_exc.value.field == "sort_strategy"


@pytest.mark.parametrize(
    "values",
    (
        ("0.4", "0.5", "0.1"),
        ("40", "50", "10"),
        ("-1", "0.5", "0.5"),
        ("", "0.5", "0.5"),
        ("0.5", "50", "0"),
        ("0.5", "0.5", "0.5"),
    ),
)
def test_scheduler_config_weight_triplet_helpers_stay_in_sync(values) -> None:
    assert _weight_outcome(normalize_service_weight_triplet, values) == _weight_outcome(
        normalize_runtime_weight_triplet,
        values,
    )


def test_scheduler_config_float_choice_helpers_stay_in_sync() -> None:
    samples = (
        (1.0, ()),
        (1.0, ("1",)),
        (1.0 + 1e-10, ("1",)),
        (1.0 + 2e-9, ("1",)),
        (1.0, ("abc",)),
        (1.0, ("abc", "1.0")),
    )

    for value, choices in samples:
        assert runtime_coercion._float_matches_choice(value, choices) == service_coercion._float_matches_choice(
            value,
            choices,
        )


def test_scheduler_config_valid_text_normalizers_stay_in_sync() -> None:
    samples = (
        (),
        (" A ", "YES", "yes", "", "  ", "b", "B"),
        ("first", "Second", "first", "second", "THIRD"),
    )

    assert runtime_coercion._normalize_valid_texts(None) == service_coercion._normalize_valid_texts(None)
    for values in samples:
        assert runtime_coercion._normalize_valid_texts(values) == service_coercion._normalize_valid_texts(values)


def _degradation_event_payload(event):
    if event is None:
        return None
    return (
        event.code,
        event.scope,
        event.field,
        event.message,
        event.count,
        event.sample,
    )


def test_scheduler_config_degradation_event_coercers_stay_in_sync() -> None:
    event = DegradationEvent(
        code="invalid_choice",
        scope="scheduler.runtime_config",
        field="graph_analysis_mode",
        message="bad graph mode",
        count=3,
        sample="bad",
    )
    samples = (
        event,
        None,
        ["not", "dict"],
        {"code": "", "scope": "scope", "message": "message"},
        {"code": "code", "scope": "", "message": "message"},
        {"code": "code", "scope": "scope", "message": ""},
        {"code": " code ", "scope": " scope ", "message": " message ", "field": None, "sample": None},
        {"code": "code", "scope": "scope", "message": "message", "field": "  ", "count": "x"},
        {"code": "code", "scope": "scope", "message": "message", "field": " field ", "count": -5, "sample": 9},
        {"code": "code", "scope": "scope", "message": "message", "count": 2},
    )

    for raw in samples:
        assert _degradation_event_payload(runtime_read._coerce_degradation_event(raw)) == _degradation_event_payload(
            service_snapshot._coerce_degradation_event(raw)
        )


def test_service_legacy_missing_policy_is_intentionally_not_runtime_behavior() -> None:
    service_collector = DegradationCollector()
    runtime_collector = DegradationCollector()

    service_value = coerce_config_field(
        "graph_analysis_mode",
        None,
        strict_mode=False,
        source="legacy-preset",
        collector=service_collector,
        missing=True,
        fallback="on",
        missing_policy=MISSING_POLICY_INHERIT_LEGACY_OMISSION,
    )
    runtime_value = coerce_runtime_config_field(
        {},
        "graph_analysis_mode",
        strict_mode=False,
        source="runtime-config",
        collector=runtime_collector,
    )

    assert service_value == runtime_value == "on"
    assert service_collector.to_list() == []
    assert runtime_collector.to_list()

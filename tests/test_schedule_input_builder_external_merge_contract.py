from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.models.enums import MergeMode
from core.services.scheduler.schedule_input_builder import build_algo_operations


class _Repo:
    def __init__(self, values):
        self.values = dict(values)
        self.calls = []

    def get(self, *args):
        self.calls.append(tuple(args))
        key = tuple(args) if len(args) != 1 else args[0]
        return self.values.get(key)


class _BuilderSvc:
    def __init__(self, *, template=None, groups=None):
        self.batch_calls = []
        self.part_op_repo = _Repo({("P001", 20): template})
        self.group_repo = _Repo(groups or {})
        self._aps_schedule_input_cache = {}

    def _get_batch_or_raise(self, batch_id):
        self.batch_calls.append(batch_id)
        return SimpleNamespace(batch_id=batch_id, part_no="P001")


class _FailingRepo:
    def get(self, *args):
        raise AssertionError(f"内部工序不应查模板或外部组：{args!r}")


class _InternalSvc:
    part_op_repo = _FailingRepo()
    group_repo = _FailingRepo()
    _aps_schedule_input_cache = {}

    def _get_batch_or_raise(self, batch_id):
        raise AssertionError(f"内部工序不应查批次模板：{batch_id!r}")


def _op(*, source="external", ext_days=2.5):
    return SimpleNamespace(
        id=2,
        op_code="OP_EXT_01",
        batch_id="B001",
        seq=20,
        op_type_id="OT_EXT",
        op_type_name="外协",
        source=source,
        machine_id=None,
        operator_id=None,
        supplier_id="SUP01",
        setup_hours=0.0,
        unit_hours=0.0,
        ext_days=ext_days,
    )


def _template(ext_group_id):
    return SimpleNamespace(ext_group_id=ext_group_id)


def _group(*, merge_mode, total_days):
    return SimpleNamespace(merge_mode=merge_mode, total_days=total_days)


def _single_result(outcome):
    assert len(outcome.value) == 1
    return outcome.value[0]


def _event_codes(outcome):
    return [event.code for event in outcome.events]


def test_internal_op_skips_template_lookup_and_has_empty_merge_fields() -> None:
    outcome = build_algo_operations(_InternalSvc(), [_op(source="internal", ext_days=None)], return_outcome=True)

    algo_op = _single_result(outcome)
    assert outcome.events == []
    assert algo_op.ext_days is None
    assert algo_op.ext_group_id is None
    assert algo_op.ext_merge_mode is None
    assert algo_op.ext_group_total_days is None
    assert algo_op.merge_context_degraded is False
    assert algo_op.merge_context_events == []


def test_external_without_group_uses_ext_days_without_degradation() -> None:
    svc = _BuilderSvc(template=_template(None))

    outcome = build_algo_operations(svc, [_op(ext_days=2.5)], return_outcome=True)

    algo_op = _single_result(outcome)
    assert outcome.events == []
    assert algo_op.ext_days == 2.5
    assert algo_op.ext_group_id is None
    assert algo_op.ext_merge_mode is None
    assert algo_op.ext_group_total_days is None
    assert algo_op.merge_context_degraded is False
    assert algo_op.merge_context_events == []
    assert svc.part_op_repo.calls == [("P001", 20)]
    assert svc.group_repo.calls == []


def test_external_separate_group_uses_ext_days_without_merged_semantics() -> None:
    svc = _BuilderSvc(
        template=_template("G001"),
        groups={"G001": _group(merge_mode=MergeMode.SEPARATE.value, total_days=9.0)},
    )

    outcome = build_algo_operations(svc, [_op(ext_days=2.5)], return_outcome=True)

    algo_op = _single_result(outcome)
    assert outcome.events == []
    assert algo_op.ext_days == 2.5
    assert algo_op.ext_group_id == "G001"
    assert algo_op.ext_merge_mode == MergeMode.SEPARATE.value
    assert algo_op.ext_group_total_days is None
    assert algo_op.merge_context_degraded is False
    assert algo_op.merge_context_events == []


def test_external_merged_group_uses_total_days_and_ignores_member_ext_days() -> None:
    svc = _BuilderSvc(
        template=_template("G001"),
        groups={"G001": _group(merge_mode=MergeMode.MERGED.value, total_days=4.0)},
    )

    outcome = build_algo_operations(svc, [_op(ext_days=2.5)], return_outcome=True)

    algo_op = _single_result(outcome)
    assert outcome.events == []
    assert algo_op.ext_days is None
    assert algo_op.ext_group_id == "G001"
    assert algo_op.ext_merge_mode == MergeMode.MERGED.value
    assert algo_op.ext_group_total_days == 4.0
    assert algo_op.merge_context_degraded is False
    assert algo_op.merge_context_events == []


def test_template_missing_non_strict_records_event_and_falls_back_to_ext_days() -> None:
    svc = _BuilderSvc(template=None)

    outcome = build_algo_operations(svc, [_op(ext_days=2.5)], return_outcome=True)

    algo_op = _single_result(outcome)
    assert "template_missing" in _event_codes(outcome)
    assert algo_op.ext_days == 2.5
    assert algo_op.ext_group_id is None
    assert algo_op.ext_merge_mode is None
    assert algo_op.ext_group_total_days is None
    assert algo_op.merge_context_degraded is True
    assert [event["code"] for event in algo_op.merge_context_events] == ["template_missing"]


def test_external_group_missing_non_strict_records_event_and_falls_back_to_ext_days() -> None:
    svc = _BuilderSvc(template=_template("G404"), groups={})

    outcome = build_algo_operations(svc, [_op(ext_days=2.5)], return_outcome=True)

    algo_op = _single_result(outcome)
    assert "external_group_missing" in _event_codes(outcome)
    assert algo_op.ext_days == 2.5
    assert algo_op.ext_group_id is None
    assert algo_op.ext_merge_mode is None
    assert algo_op.ext_group_total_days is None
    assert algo_op.merge_context_degraded is True
    assert [event["code"] for event in algo_op.merge_context_events] == ["external_group_missing"]


def test_invalid_group_total_days_non_strict_clears_merge_fields_and_records_merge_event() -> None:
    svc = _BuilderSvc(
        template=_template("G001"),
        groups={"G001": _group(merge_mode=MergeMode.MERGED.value, total_days="bad-number")},
    )

    outcome = build_algo_operations(svc, [_op(ext_days=2.5)], return_outcome=True)

    algo_op = _single_result(outcome)
    assert "invalid_number" in _event_codes(outcome)
    assert algo_op.ext_days == 2.5
    assert algo_op.ext_group_id is None
    assert algo_op.ext_merge_mode is None
    assert algo_op.ext_group_total_days is None
    assert algo_op.merge_context_degraded is True
    assert [event["code"] for event in algo_op.merge_context_events] == ["invalid_number"]
    assert [event["field"] for event in algo_op.merge_context_events] == ["ext_group_total_days"]


@pytest.mark.parametrize(
    ("template", "groups", "expected_field"),
    [
        (None, {}, "template"),
        (_template("G404"), {}, "ext_group_id"),
        (_template("G001"), {"G001": _group(merge_mode=MergeMode.MERGED.value, total_days="bad-number")}, "ext_group_total_days"),
    ],
)
def test_merge_context_failures_raise_in_strict_mode(template, groups, expected_field) -> None:
    svc = _BuilderSvc(template=template, groups=groups)

    with pytest.raises(ValidationError) as exc_info:
        build_algo_operations(svc, [_op(ext_days=2.5)], strict_mode=True, return_outcome=True)

    assert exc_info.value.field == expected_field

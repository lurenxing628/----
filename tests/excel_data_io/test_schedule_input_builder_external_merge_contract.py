"""Frozen external contexts: separate uses member days; merged uses its captured total."""

import pytest

from core.errors import ValidationError
from core.services.scheduler.contracts.external_context import context_group_key
from core.services.scheduler.run.schedule_input_builder import build_algo_operations
from tests.schedule.service.external_context_support import (
    SnapshotService,
    external_operation,
    merged_snapshot,
    snapshot,
)


def test_internal_op_does_not_access_external_context():
    outcome = build_algo_operations(object(), [external_operation(source="internal")], return_outcome=True)
    op = outcome.value[0]
    assert outcome.events == [] and op.ext_days is None
    assert op.ext_group_id is None and op.ext_merge_mode is None


@pytest.mark.parametrize("mode", [None, "separate", "merged"])
def test_algorithm_uses_frozen_context_and_never_active_template(mode, monkeypatch):
    from core.services.scheduler.run import schedule_template_lookup

    def legacy_object(*args, **kwargs):
        raise AssertionError("Algorithm input consumes frozen facts directly")

    monkeypatch.setattr(schedule_template_lookup, "PartOperation", legacy_object)
    monkeypatch.setattr(schedule_template_lookup, "ExternalGroup", legacy_object)
    row = snapshot() if mode is None else merged_snapshot(merge_mode=mode)
    outcome = build_algo_operations(SnapshotService(row), [external_operation()], return_outcome=True)
    op = outcome.value[0]
    assert outcome.events == [] and op.merge_context_degraded is False
    assert op.ext_days == (None if mode == "merged" else 2.5)
    assert op.ext_group_total_days == (4 if mode == "merged" else None)
    assert op.ext_group_id == context_group_key(row)


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("row", [
    None, snapshot(template_operation_id=None), snapshot(template_status="deleted"),
    merged_snapshot(group_part_no="P999"), merged_snapshot(start_sequence=30, end_sequence=40),
    merged_snapshot(total_days="bad-number"), merged_snapshot(total_days=None),
    merged_snapshot(merge_mode="unknown"), merged_snapshot(group_ref=None),
    merged_snapshot(group_id=None), merged_snapshot(template_operation_ref=None),
])
def test_unproven_context_never_falls_back_to_single_days(row, strict):
    with pytest.raises(ValidationError) as error:
        build_algo_operations(SnapshotService(row), [external_operation()], strict_mode=strict)
    assert error.value.field == "external_context"

"""Lookup consumes captured batch facts, including stable identities and local cache."""

import pytest

from core.errors import ValidationError
from core.services.scheduler.contracts.external_context import context_group_key
from core.services.scheduler.run.schedule_template_lookup import lookup_template_group_context_for_op
from tests.schedule.service.external_context_support import (
    SnapshotService,
    external_operation,
    merged_snapshot,
    snapshot,
)


@pytest.mark.parametrize("mode", [None, "merged", "separate"])
def test_lookup_uses_frozen_facts_without_reading_live_template(mode):
    row = snapshot() if mode is None else merged_snapshot(merge_mode=mode)
    svc = SnapshotService(row)
    first = lookup_template_group_context_for_op(svc, external_operation())
    second = lookup_template_group_context_for_op(svc, external_operation())
    assert first.template.ext_group_id == context_group_key(row)
    assert second.template.ext_group_id == first.template.ext_group_id
    assert (first.group is None) == (mode is None)
    if first.group:
        assert first.group.total_days == row["total_days"]
        assert first.group.merge_mode == mode
    assert first.events == [] and not first.merge_context_degraded
    assert svc.batch_calls == ["B001"]


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("row", [
    None, snapshot(template_status="deleted"), merged_snapshot(group_part_no="P999"),
    merged_snapshot(start_sequence=30), merged_snapshot(group_ref=None),
])
def test_missing_or_invalid_facts_stop_lookup_without_fallback(row, strict):
    with pytest.raises(ValidationError) as error:
        lookup_template_group_context_for_op(SnapshotService(row), external_operation(), strict_mode=strict)
    assert error.value.field == "external_context"
    assert "SECRET_TOKEN" not in error.value.message


def test_distinct_permanent_group_or_frozen_rule_cannot_share_group_key():
    original = merged_snapshot()
    assert context_group_key(original) != context_group_key(merged_snapshot(group_ref="b" * 48))
    assert context_group_key(original) != context_group_key(merged_snapshot(total_days=9))
    assert context_group_key(original) == context_group_key(merged_snapshot(origin="instance_copy"))

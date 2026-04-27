from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.models.enums import MergeMode
from core.services.scheduler.run.schedule_template_lookup import lookup_template_group_context_for_op


class _Repo:
    def __init__(self, values):
        self.values = dict(values)
        self.calls = []

    def get(self, *args):
        self.calls.append(tuple(args))
        key = tuple(args) if len(args) != 1 else args[0]
        return self.values.get(key)


class _LookupSvc:
    def __init__(self, *, template=None, groups=None, cache=None):
        self.batch_repo_calls = []
        self.part_op_repo = _Repo({("P001", 20): template})
        self.group_repo = _Repo(groups or {})
        self._aps_schedule_input_cache = cache

    def _get_batch_or_raise(self, batch_id):
        self.batch_repo_calls.append(batch_id)
        return SimpleNamespace(batch_id=batch_id, part_no="P001")


def _op():
    return SimpleNamespace(id=2, op_code="OP_EXT_01", batch_id="B001", seq=20)


def _template(ext_group_id):
    return SimpleNamespace(ext_group_id=ext_group_id)


def _group(*, merge_mode=MergeMode.MERGED.value, total_days=4.0):
    return SimpleNamespace(merge_mode=merge_mode, total_days=total_days)


def _codes(outcome):
    return [event.code for event in outcome.events]


def test_lookup_template_missing_non_strict_returns_degraded_event() -> None:
    outcome = lookup_template_group_context_for_op(_LookupSvc(template=None), _op(), strict_mode=False)

    assert outcome.template is None
    assert outcome.group is None
    assert outcome.merge_context_degraded is True
    assert _codes(outcome) == ["template_missing"]
    assert outcome.events[0].field == "template"


def test_lookup_without_ext_group_id_returns_template_without_degradation() -> None:
    template = _template(None)

    outcome = lookup_template_group_context_for_op(_LookupSvc(template=template), _op(), strict_mode=False)

    assert outcome.template is template
    assert outcome.group is None
    assert outcome.merge_context_degraded is False
    assert outcome.events == []


@pytest.mark.parametrize("merge_mode", [MergeMode.MERGED.value, MergeMode.SEPARATE.value])
def test_lookup_existing_group_returns_template_and_group_without_degradation(merge_mode) -> None:
    template = _template("G001")
    group = _group(merge_mode=merge_mode)

    outcome = lookup_template_group_context_for_op(
        _LookupSvc(template=template, groups={"G001": group}),
        _op(),
        strict_mode=False,
    )

    assert outcome.template is template
    assert outcome.group is group
    assert outcome.merge_context_degraded is False
    assert outcome.events == []


def test_lookup_external_group_missing_non_strict_returns_degraded_event() -> None:
    template = _template("G404")

    outcome = lookup_template_group_context_for_op(_LookupSvc(template=template, groups={}), _op(), strict_mode=False)

    assert outcome.template is template
    assert outcome.group is None
    assert outcome.merge_context_degraded is True
    assert _codes(outcome) == ["external_group_missing"]
    assert outcome.events[0].field == "ext_group_id"


@pytest.mark.parametrize(
    ("template", "groups", "expected_field"),
    [
        (None, {}, "template"),
        (_template("G404"), {}, "ext_group_id"),
    ],
)
def test_lookup_missing_paths_raise_in_strict_mode(template, groups, expected_field) -> None:
    with pytest.raises(ValidationError) as exc_info:
        lookup_template_group_context_for_op(_LookupSvc(template=template, groups=groups), _op(), strict_mode=True)

    assert exc_info.value.field == expected_field


def test_lookup_reuses_batch_template_and_group_cache() -> None:
    cache = {}
    template = _template("G001")
    group = _group()
    svc = _LookupSvc(template=template, groups={"G001": group}, cache=cache)

    first = lookup_template_group_context_for_op(svc, _op(), strict_mode=False)
    second = lookup_template_group_context_for_op(svc, _op(), strict_mode=False)

    assert first.template is template
    assert first.group is group
    assert second.template is template
    assert second.group is group
    assert svc.batch_repo_calls == ["B001"]
    assert svc.part_op_repo.calls == [("P001", 20)]
    assert svc.group_repo.calls == [("G001",)]

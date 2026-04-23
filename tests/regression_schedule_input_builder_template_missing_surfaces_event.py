from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.schedule_input_builder import build_algo_operations


class _NullRepo:
    def get(self, *args, **kwargs):
        return None


class _StubSvc:
    def __init__(self):
        self.part_op_repo = _NullRepo()
        self.group_repo = _NullRepo()
        self._aps_schedule_input_cache = {}

    @staticmethod
    def _get_batch_or_raise(batch_id: str):
        return SimpleNamespace(part_no="P001")


def _external_op() -> SimpleNamespace:
    return SimpleNamespace(
        id=2,
        op_code="OP_EXT_01",
        batch_id="B001",
        seq=20,
        op_type_id="OT_EXT",
        op_type_name="external",
        source="external",
        machine_id=None,
        operator_id=None,
        supplier_id="SUP01",
        setup_hours=0.0,
        unit_hours=0.0,
        ext_days=2.0,
    )


def test_schedule_input_builder_template_missing_surfaces_event() -> None:
    svc = _StubSvc()
    outcome = build_algo_operations(svc, [_external_op()], strict_mode=False, return_outcome=True)
    assert outcome.has_events is True
    codes = [event.code for event in outcome.events]
    assert "template_missing" in codes, codes

    algo_op = outcome.value[0]
    assert algo_op.merge_context_degraded is True, algo_op
    merge_codes = [str(event.get("code") or "") for event in algo_op.merge_context_events]
    assert "template_missing" in merge_codes, algo_op.merge_context_events
    assert float(algo_op.ext_days or 0.0) == 2.0, algo_op.ext_days


def test_schedule_input_builder_template_missing_strict_mode_fail_fast() -> None:
    svc = _StubSvc()
    with pytest.raises(ValidationError) as exc_info:
        build_algo_operations(svc, [_external_op()], strict_mode=True, return_outcome=True)

    assert exc_info.value.field == "template", exc_info.value.field

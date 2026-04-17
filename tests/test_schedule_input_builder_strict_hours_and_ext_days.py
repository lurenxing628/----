from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.schedule_input_builder import build_algo_operations


class _StubSvc:
    def __init__(self):
        self.part_op_repo = self
        self.group_repo = self

    def _get_batch_or_raise(self, batch_id):
        return SimpleNamespace(batch_id=batch_id, part_no="P001")

    def get(self, *args):
        if len(args) == 2:
            return SimpleNamespace(ext_group_id=None)
        return None


class _LegacyOnlySvc:
    def _get_template_and_group_for_op(self, op):
        return None, None


def test_schedule_input_builder_strict_blank_setup_hours_rejected() -> None:
    svc = _StubSvc()
    internal = SimpleNamespace(
        id=1,
        op_code="OP_INT_01",
        batch_id="B001",
        seq=10,
        op_type_id="OT01",
        op_type_name="车削",
        source="internal",
        machine_id="M001",
        operator_id="O001",
        supplier_id=None,
        setup_hours="   ",
        unit_hours=0.5,
        ext_days=None,
    )

    with pytest.raises(ValidationError) as exc_info:
        build_algo_operations(svc, [internal], strict_mode=True)

    assert exc_info.value.field == "setup_hours", f"内部工序空白 setup_hours 未被 strict_mode 拒绝：{exc_info.value.field!r}"


def test_schedule_input_builder_strict_blank_ext_days_rejected() -> None:
    svc = _StubSvc()
    external = SimpleNamespace(
        id=2,
        op_code="OP_EXT_01",
        batch_id="B001",
        seq=20,
        op_type_id="OT_EXT",
        op_type_name="外协",
        source="external",
        machine_id=None,
        operator_id=None,
        supplier_id="SUP01",
        setup_hours=0.0,
        unit_hours=0.0,
        ext_days="   ",
    )

    with pytest.raises(ValidationError) as exc_info:
        build_algo_operations(svc, [external], strict_mode=True)

    assert exc_info.value.field == "ext_days", f"外协工序空白 ext_days 未被 strict_mode 拒绝：{exc_info.value.field!r}"


def test_schedule_input_builder_does_not_fallback_to_legacy_private_lookup() -> None:
    external = SimpleNamespace(
        id=3,
        op_code="OP_EXT_02",
        batch_id="B001",
        seq=30,
        op_type_id="OT_EXT",
        op_type_name="外协",
        source="external",
        machine_id=None,
        operator_id=None,
        supplier_id="SUP01",
        setup_hours=0.0,
        unit_hours=0.0,
        ext_days=1.0,
    )

    with pytest.raises(AttributeError):
        build_algo_operations(_LegacyOnlySvc(), [external])

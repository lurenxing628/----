"""回归测试：build_algo_operations 对工序数值字段做安全解析——内部工序的空白/非数字 setup_hours、unit_hours 必须直接报错；外部工序（source 大小写混用仍识别为 external）空白 ext_days 兼容回退为 1.0，并保留 blank_required 等结构化退化事件。"""

from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError


class _StubSvc:
    def __init__(self):
        self.template_lookup_keys = []
        self.part_op_repo = self
        self.group_repo = self

    def _get_batch_or_raise(self, batch_id):
        return SimpleNamespace(batch_id=batch_id, part_no="P001")

    def get(self, *args):
        if len(args) == 2:
            self.template_lookup_keys.append(args)
            return SimpleNamespace(ext_group_id=None)
        return None


def test_schedule_input_builder_safe_float_parse() -> None:

    from core.services.scheduler.schedule_input_builder import build_algo_operations

    svc = _StubSvc()

    invalid_internal = SimpleNamespace(
        id=1,
        op_code="OP_INT_01",
        batch_id="B001",
        seq=1,
        op_type_id="OT01",
        op_type_name="车削",
        source="internal",
        machine_id="M001",
        operator_id="O001",
        supplier_id=None,
        setup_hours="   ",
        unit_hours="abc",
        ext_days=None,
    )
    with pytest.raises(ValidationError) as exc_info:
        build_algo_operations(svc, [invalid_internal], return_outcome=True)
    assert exc_info.value.field == "setup_hours"

    internal = SimpleNamespace(
        id=1,
        op_code="OP_INT_01",
        batch_id="B001",
        seq=1,
        op_type_id="OT01",
        op_type_name="车削",
        source="internal",
        machine_id="M001",
        operator_id="O001",
        supplier_id=None,
        setup_hours="0.5",
        unit_hours="1",
        ext_days=None,
    )
    external = SimpleNamespace(
        id=2,
        op_code="OP_EXT_01",
        batch_id="B001",
        seq=2,
        op_type_id="OT_EXT",
        op_type_name="外协",
        source="External",  # 大小写混用：仍应识别为 external
        machine_id=None,
        operator_id=None,
        supplier_id="SUP01",
        setup_hours=None,
        unit_hours=None,
        ext_days="  ",  # 空白字符串：应按兼容读取回退为 1.0（不应抛异常）
    )

    outcome = build_algo_operations(svc, [internal, external], return_outcome=True)
    out = outcome.value
    assert len(out) == 2, f"build_algo_operations 输出数量异常：{len(out)}"
    assert svc.template_lookup_keys == [("P001", 2)], "external 工序应触发真实模板查找（source 大小写需容错）"
    assert outcome.has_events is True, "兼容读取坏值后应保留结构化退化事件"

    op0 = out[0]
    op1 = out[1]

    assert float(op0.setup_hours) == 0.5, f"setup_hours 解析异常：{op0.setup_hours!r}"
    assert float(op0.unit_hours) == 1.0, f"unit_hours 解析异常：{op0.unit_hours!r}"
    assert float(op1.ext_days or 0.0) == 1.0, f"ext_days 兼容回退异常：{op1.ext_days!r}"
    codes = [event.code for event in outcome.events]
    assert "blank_required" in codes, f"兼容读取事件缺少 blank_required：{codes!r}"

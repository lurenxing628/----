"""回归测试：模型层数值解析不得静默兜底——_helpers.parse_int 内部 Decimal 异常应原样抛出而非默认为 0；Batch/BatchOperation/WorkCalendar/OperatorCalendar/PartOperation/Supplier 的 from_row 对坏值（如「坏数据」）必须抛 ValueError，但对空字符串仍保留历史默认（quantity=0、shift_hours=8.0、default_days=1.0、ext_days=None 等）。"""

from __future__ import annotations

import pytest

from core.models import _helpers
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from core.models.calendar import OperatorCalendar, WorkCalendar
from core.models.part_operation import PartOperation
from core.models.supplier import Supplier


def test_decimal_internal_error_is_not_silently_defaulted(monkeypatch) -> None:
    def fail_decimal(_value):
        raise RuntimeError("decimal parser failed")

    monkeypatch.setattr(_helpers, "Decimal", fail_decimal)
    with pytest.raises(RuntimeError):
        _helpers.parse_int("1.0", default=0)


def test_critical_model_numbers_reject_bad_values() -> None:
    with pytest.raises(ValueError):
        Batch.from_row({"batch_id": "B001", "part_no": "P001", "quantity": "坏数据"})

    with pytest.raises(ValueError):
        BatchOperation.from_row(
            {
                "op_code": "OP1",
                "batch_id": "B001",
                "seq": 1,
                "unit_hours": "坏数据",
            }
        )
    with pytest.raises(ValueError):
        BatchOperation.from_row(
            {
                "op_code": "OP1",
                "batch_id": "B001",
                "seq": "坏数据",
            }
        )

    with pytest.raises(ValueError):
        WorkCalendar.from_row({"date": "2026-01-01", "shift_hours": "坏数据"})

    with pytest.raises(ValueError):
        OperatorCalendar.from_row({"operator_id": "OP1", "date": "2026-01-01", "shift_hours": "坏数据"})

    with pytest.raises(ValueError):
        PartOperation.from_row({"part_no": "P001", "seq": "坏数据"})

    with pytest.raises(ValueError):
        PartOperation.from_row({"part_no": "P001", "seq": 1, "setup_hours": "坏数据"})

    with pytest.raises(ValueError):
        PartOperation.from_row({"part_no": "P001", "seq": 1, "unit_hours": "坏数据"})

    with pytest.raises(ValueError):
        PartOperation.from_row({"part_no": "P001", "seq": 1, "ext_days": "坏数据"})

    with pytest.raises(ValueError):
        Supplier.from_row({"supplier_id": "SUP1", "name": "供应商", "default_days": "坏数据"})


def test_critical_model_blank_values_keep_legacy_defaults() -> None:
    batch = Batch.from_row({"batch_id": "B001", "part_no": "P001", "quantity": ""})
    op = BatchOperation.from_row({"op_code": "OP1", "batch_id": "B001", "seq": 1, "unit_hours": ""})
    op_with_blank_seq = BatchOperation.from_row({"op_code": "OP1", "batch_id": "B001", "seq": ""})
    part_op = PartOperation.from_row({"part_no": "P001", "seq": "", "setup_hours": "", "unit_hours": "", "ext_days": ""})
    calendar = WorkCalendar.from_row({"date": "2026-01-01", "shift_hours": ""})
    supplier = Supplier.from_row({"supplier_id": "SUP1", "name": "供应商", "default_days": ""})

    assert batch.quantity == 0
    assert op.unit_hours == 0.0
    assert op_with_blank_seq.seq == 0
    assert part_op.seq == 0
    assert part_op.setup_hours == 0.0
    assert part_op.unit_hours == 0.0
    assert part_op.ext_days is None
    assert calendar.shift_hours == 8.0
    assert supplier.default_days == 1.0

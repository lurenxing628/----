"""完整、合法的排产领域对象夹具。

默认值与生产构造边界（run_input_rows.operation_model → schedule_input_builder）产出的规范值一致：
文本编号非空无首尾空格，未指定的设备/人员/分件/供应商为 None（不是空串），工种必填。
测试只覆盖与用例相关的字段；不认识的字段名直接报错，避免拼出生产里不存在的对象。
"""
from __future__ import annotations

from dataclasses import fields
from typing import Any, Dict

from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult, ScheduleSummary
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation


def _build(cls, defaults: Dict[str, Any], overrides: Dict[str, Any]):
    unknown = sorted(set(overrides) - {item.name for item in fields(cls)})
    if unknown:
        raise TypeError(f"{cls.__name__} 没有这些字段：{unknown}")
    values = dict(defaults)
    values.update(overrides)
    return cls(**values)


def make_algo_op(**overrides: Any) -> OpForScheduleAlgo:
    """算法输入工序；默认是 B1 批次第 1 道、未指定资源的自制工序。"""
    op_id = overrides.get("id", 1)
    defaults = dict(
        id=op_id, op_code=f"OP{op_id}", batch_id="B1", piece_id=None, seq=1, op_type_id="T1", op_type_name="T1",
        source="internal", machine_id=None, operator_id=None, supplier_id=None, setup_hours=0.0, unit_hours=1.0,
        ext_days=None, ext_group_id=None, ext_merge_mode=None, ext_group_total_days=None, material_ready_date=None,
    )
    return _build(OpForScheduleAlgo, defaults, overrides)


def make_batch_operation(**overrides: Any) -> BatchOperation:
    """批次工序行；字段与 run_input_rows.operation_model 构造的一致。"""
    op_id = overrides.get("id", 1)
    defaults = dict(
        id=op_id, op_code=f"OP{op_id}", batch_id="B1", piece_id=None, seq=1, op_type_id="T1", op_type_name="T1",
        source="internal", machine_id=None, operator_id=None, supplier_id=None, setup_hours=0.0, unit_hours=1.0,
        ext_days=None, status="pending", created_at=None,
    )
    return _build(BatchOperation, defaults, overrides)


def make_batch(**overrides: Any) -> Batch:
    """批次；默认数量 1、普通优先级、已齐套、无交期。"""
    defaults = dict(
        batch_id="B1", part_no="P1", part_name=None, quantity=1, due_date=None, priority="normal",
        ready_status="yes", ready_date=None, status="pending", remark=None, created_at=None, updated_at=None,
    )
    return _build(Batch, defaults, overrides)


def make_schedule_result(**overrides: Any) -> ScheduleResult:
    """单道工序排程结果；默认对应 make_algo_op() 的那道工序。"""
    op_id = overrides.get("op_id", 1)
    defaults = dict(op_id=op_id, op_code=f"OP{op_id}", batch_id="B1", seq=1)
    return _build(ScheduleResult, defaults, overrides)


def make_schedule_summary(**overrides: Any) -> ScheduleSummary:
    """排程摘要；默认是 0 道工序的成功摘要。"""
    defaults = dict(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[],
                    duration_seconds=0.0, failure_details=[])
    return _build(ScheduleSummary, defaults, overrides)

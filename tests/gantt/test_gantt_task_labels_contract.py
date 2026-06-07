"""回归测试：守护甘特工序标签 detail_operation_label / public_task_label——seq 为 0 时仍显示「0（工种）」而非误判缺失，seq 为 None 时分别回退为「-」和「未命名工序」。"""

from __future__ import annotations

from core.services.scheduler.gantt_task_labels import detail_operation_label, public_task_label


def test_gantt_task_labels_preserve_zero_sequence_number() -> None:
    row = {"seq": 0, "op_type_name": "检验"}

    assert detail_operation_label(row) == "0（检验）"
    assert public_task_label(row) == "0（检验）"


def test_gantt_task_labels_treat_none_as_missing_value() -> None:
    assert detail_operation_label({"seq": None, "op_type_name": ""}) == "-"
    assert public_task_label({"seq": None, "op_type_name": "", "batch_id": None}) == "未命名工序"

from __future__ import annotations

from typing import List

EMPTY_ROUTE_ERROR = "工艺路线为空或格式无效"
MISSING_START_SEQ_ERROR = "工艺路线格式无效：必须以工序号开头"
GENERIC_FORMAT_ERROR = "无法识别工艺路线格式，请使用'工序号+工种名'格式，如'5数铣10钳20数车'"


def missing_tail_op_error(seq: str) -> str:
    return f"工艺路线尾部工序号 {seq} 缺少工种名"


def invalid_seq_warning(seq: str) -> str:
    return f"工序号“{seq}”无法解析，将跳过"


def empty_op_warning(seq: int) -> str:
    return f"工序号 {seq} 的工种为空，将跳过"


def duplicate_seq_warning(seq: int) -> str:
    return f"工序号 {seq} 重复出现，将保留第一个"


def strict_unknown_op_error(op_type_name: str) -> str:
    return f"工种“{op_type_name}”未在系统中配置，严格模式已拒绝默认标记为外部工序"


def relaxed_unknown_op_warning(op_type_name: str) -> str:
    return f"工种“{op_type_name}”未在系统中配置，已默认标记为外部工序"


def strict_missing_supplier_error(op_type_name: str) -> str:
    return f"工种“{op_type_name}”未找到供应商配置，严格模式已拒绝按默认 1.0 天初始化外协周期"


def relaxed_missing_supplier_warning(op_type_name: str) -> str:
    return f"工种“{op_type_name}”未找到供应商配置，已按默认 1.0 天初始化外协周期"


def supplier_missing_days_warning(supplier_id: str, op_type_name: str) -> str:
    return f"供应商“{supplier_id}”未配置默认周期，工种“{op_type_name}”已按 1.0 天处理"


def supplier_blank_days_warning(supplier_id: str, op_type_name: str) -> str:
    return f"供应商“{supplier_id}”默认周期为空，工种“{op_type_name}”已按 1.0 天处理"


def supplier_unparseable_days_warning(supplier_id: str, op_type_name: str) -> str:
    return f"供应商“{supplier_id}”默认周期无法解析，工种“{op_type_name}”已按 1.0 天处理"


def supplier_invalid_days_warning(supplier_id: str, op_type_name: str) -> str:
    return f"供应商“{supplier_id}”默认周期无效，工种“{op_type_name}”已按 1.0 天处理"


def strict_supplier_issue_messages(issue_messages: List[str], *, op_type_name: str) -> List[str]:
    out: List[str] = []
    for raw_msg in issue_messages or []:
        text = str(raw_msg or "").strip()
        if not text:
            continue
        out.append(text.replace("已按 1.0 天处理", "严格模式已拒绝按 1.0 天处理"))
    if out:
        return out
    return [f"工种“{op_type_name}”供应商默认周期配置无效，严格模式已拒绝按 1.0 天处理"]

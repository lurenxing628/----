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
    return f"工种“{op_type_name}”还没有在系统里配置。当前要求先把工种资料补完整，请先补工种后再导入或创建。"


def relaxed_unknown_op_warning(op_type_name: str) -> str:
    return f"工种“{op_type_name}”还没有在系统里配置，本次先按外协工序处理。请尽快补好工种配置。"


def strict_missing_supplier_error(op_type_name: str) -> str:
    return f"外协工序“{op_type_name}”没有可用的外协供应商。已开启严格校验，请先补外协供应商和周期后再继续。"


def relaxed_missing_supplier_warning(op_type_name: str) -> str:
    return f"工种“{op_type_name}”没有找到可用的外协供应商，本次会先按 1 天安排。建议补好供应商和周期。"


def supplier_missing_days_warning(supplier_id: str, op_type_name: str) -> str:
    return f"供应商“{supplier_id}”没有填写默认周期，工种“{op_type_name}”本次会先按 1 天安排。请补成真实周期。"


def supplier_blank_days_warning(supplier_id: str, op_type_name: str) -> str:
    return f"供应商“{supplier_id}”的默认周期为空，工种“{op_type_name}”本次会先按 1 天安排。请补成真实周期。"


def supplier_unparseable_days_warning(supplier_id: str, op_type_name: str) -> str:
    return f"供应商“{supplier_id}”的默认周期格式不正确，工种“{op_type_name}”本次会先按 1 天安排。请补成真实周期。"


def supplier_invalid_days_warning(supplier_id: str, op_type_name: str) -> str:
    return f"供应商“{supplier_id}”的默认周期无效（必须大于 0），工种“{op_type_name}”本次会先按 1 天安排。请补成真实周期。"


def strict_supplier_issue_messages(issue_messages: List[str], *, op_type_name: str) -> List[str]:
    out: List[str] = []
    for raw_msg in issue_messages or []:
        text = str(raw_msg or "").strip()
        if not text:
            continue
        clean = (
            text.rstrip("。")
            .replace("先临时按 1 天处理", "")
            .replace("已按 1.0 天处理", "")
            .replace("会暂按 1 天安排", "")
            .replace("本次会先按 1 天安排", "")
            .replace("请补成真实周期", "")
            .replace("建议补好供应商和周期", "")
            .rstrip("，；。 ")
        )
        out.append(f"{clean}。已开启严格校验，请先把这个周期补正确。")
    if out:
        return out
    return [f"工种“{op_type_name}”的外协周期不正确。当前不能继续导入，请先补正确后再继续。"]

"""周派工单资源段重分组（fusion-dispatch-print-sheet，模块 N）。

输入 #16 的八中文键段行（消费不改造，零内部键是 by-design），按「设备」/
「人员」展示串重分组为打印资源段（一资源一页）。厂内资源串含 id，同名异 id
不并组；外协/无设备与未派人行统一归「外协/未分配」兜底段排最后——
「外协 {supplier}」串无 supplier_id 且 Suppliers.name 无唯一约束，按供应商串
各自成段会把重名供应商错并到一张纸（与 gantt_tasks machine_id 空即兜底同语义），
段内每行「设备」列仍保留各自供应商串做参照。

输出行只保留 7 个计划字段（drop「现场状态」）——4.11 加粗约束：派工单第一版
只含计划任务不含现场事实，纸面状态在车间会立刻过期误导。
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

FALLBACK_RESOURCE_LABEL = "外协/未分配"

_GROUP_COLUMN_BY_VIEW = {"machine": "设备", "operator": "人员"}

_PRINT_ROW_KEYS = ("日期", "批次号", "图号", "工序", "设备", "人员", "时段")


def _print_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: row.get(key, "") for key in _PRINT_ROW_KEYS}


def _resource_label(row: Mapping[str, Any], group_column: str) -> str:
    label = str(row.get(group_column) or "").strip() or FALLBACK_RESOURCE_LABEL
    # machine 视图：外协行无 supplier_id（重名供应商会错并组），统一归兜底段
    if group_column == "设备" and label.startswith("外协"):
        return FALLBACK_RESOURCE_LABEL
    return label


def _sheet_row_sort_key(row: Mapping[str, Any]) -> Any:
    # 「全天」= 00:00 起，归一为空串排当日最前；其余 HH:MM-HH:MM 字典序即时间序
    slot = str(row.get("时段") or "")
    return (str(row.get("日期") or ""), "" if slot == "全天" else slot, str(row.get("批次号") or ""))


def build_week_plan_print_sheets(
    rows: Sequence[Mapping[str, Any]],
    *,
    group_by: str,
    day: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """重分组为 [{"resource_label", "rows"}]，兜底段固定最后，其余按展示串序。

    day 给定时只留该日行（格式与出周校验是路由层职责，本函数只做等值过滤）；
    过滤后空组不出现（无任务资源不出纸）。段内行按 日期→时段 重排——上游
    周计划排序键是 日期→设备→人员→批次→工序（无时段），重分组后同段同日
    内的时间顺序必须在此补排，否则纸面任务次序会乱。
    """
    group_column = _GROUP_COLUMN_BY_VIEW.get(str(group_by))
    if group_column is None:
        raise ValueError(f"未知派工单视图：{group_by}（仅支持 machine / operator）")
    sheets: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        if day is not None and str(row.get("日期") or "") != day:
            continue
        sheets.setdefault(_resource_label(row, group_column), []).append(_print_row(row))
    ordered = sorted(label for label in sheets if label != FALLBACK_RESOURCE_LABEL)
    if FALLBACK_RESOURCE_LABEL in sheets:
        ordered.append(FALLBACK_RESOURCE_LABEL)
    return [
        {"resource_label": label, "rows": sorted(sheets[label], key=_sheet_row_sort_key)}
        for label in ordered
    ]


__all__ = ["FALLBACK_RESOURCE_LABEL", "build_week_plan_print_sheets"]

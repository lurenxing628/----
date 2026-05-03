from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple

ButtonType = Literal["primary", "secondary", "danger", "success", "ghost"]


@dataclass(frozen=True)
class ExcelActionSpec:
    label: str
    endpoint: str
    button_type: ButtonType = "secondary"
    target: Optional[str] = None


@dataclass(frozen=True)
class ExcelCardSpec:
    title: str
    desc: str
    actions: Tuple[ExcelActionSpec, ...]


def _resolve_cards(specs: Tuple[ExcelCardSpec, ...]) -> List[Dict[str, object]]:
    return [
        {
            "title": spec.title,
            "desc": spec.desc,
            "actions": [
                {
                    "label": action.label,
                    "endpoint": action.endpoint,
                    "button_type": action.button_type,
                    "target": action.target,
                }
                for action in spec.actions
            ],
        }
        for spec in specs
    ]


def process_parts_excel_cards() -> List[Dict[str, object]]:
    return _resolve_cards(
        (
            ExcelCardSpec(
                title="零件工艺路线",
                desc="批量维护图号、名称和工艺路线字符串；确认导入后会解析生成零件工序模板和外协工序组。",
                actions=(
                    ExcelActionSpec("导入/导出", "process.excel_routes_page", "primary"),
                    ExcelActionSpec("导出当前路线", "process.excel_routes_export", "secondary"),
                ),
            ),
            ExcelCardSpec(
                title="零件工序工时",
                desc="批量维护已有自制工序的换型时间和单件工时；追加模式只补齐空工时。",
                actions=(
                    ExcelActionSpec("导入/导出", "process.excel_part_op_hours_page", "primary"),
                    ExcelActionSpec("导出当前工时", "process.excel_part_op_hours_export", "secondary"),
                ),
            ),
            ExcelCardSpec(
                title="零件工序模板",
                desc="导出当前工序模板，用于复核工序、归属、供应商和外协周期。",
                actions=(
                    ExcelActionSpec("导出工序模板", "process.excel_part_ops_export", "secondary"),
                ),
            ),
        )
    )


def process_op_type_excel_cards() -> List[Dict[str, object]]:
    return _resolve_cards(
        (
            ExcelCardSpec(
                title="工种配置",
                desc="批量维护工种编号、工种名称和归属；用于工艺路线解析时判断自制或外协。",
                actions=(
                    ExcelActionSpec("导入/导出", "process.excel_op_type_page", "primary"),
                    ExcelActionSpec("导出当前工种", "process.excel_op_type_export", "secondary"),
                ),
            ),
        )
    )


def process_supplier_excel_cards() -> List[Dict[str, object]]:
    return _resolve_cards(
        (
            ExcelCardSpec(
                title="供应商配置",
                desc="批量维护外协供应商、默认周期、状态和对应工种；用于外协工序自动匹配。",
                actions=(
                    ExcelActionSpec("导入/导出", "process.excel_supplier_page", "primary"),
                    ExcelActionSpec("导出当前供应商", "process.excel_supplier_export", "secondary"),
                ),
            ),
        )
    )


def equipment_excel_cards() -> List[Dict[str, object]]:
    return _resolve_cards(
        (
            ExcelCardSpec(
                title="设备信息",
                desc="批量维护设备编号、设备名称、工种、班组和状态。",
                actions=(
                    ExcelActionSpec("导入/导出", "equipment.excel_machine_page", "primary"),
                    ExcelActionSpec("导出当前设备", "equipment.excel_machine_export", "secondary"),
                ),
            ),
            ExcelCardSpec(
                title="设备人员关联",
                desc="按设备视角批量维护可操作人员、技能等级和主操设备。",
                actions=(
                    ExcelActionSpec("导入/导出", "equipment.excel_link_page", "primary"),
                    ExcelActionSpec("导出当前关联", "equipment.excel_link_export", "secondary"),
                ),
            ),
        )
    )


def personnel_excel_cards() -> List[Dict[str, object]]:
    return _resolve_cards(
        (
            ExcelCardSpec(
                title="人员基本信息",
                desc="批量维护工号、姓名、状态、班组和备注。",
                actions=(
                    ExcelActionSpec("导入/导出", "personnel.excel_operator_page", "primary"),
                    ExcelActionSpec("导出当前人员", "personnel.excel_operator_export", "secondary"),
                ),
            ),
            ExcelCardSpec(
                title="人员设备关联",
                desc="按人员视角批量维护可操作设备、技能等级和主操设备。",
                actions=(
                    ExcelActionSpec("导入/导出", "personnel.excel_link_page", "primary"),
                    ExcelActionSpec("导出当前关联", "personnel.excel_link_export", "secondary"),
                ),
            ),
            ExcelCardSpec(
                title="人员专属工作日历",
                desc="批量维护个人请假、加班、轮班等日历覆盖规则。",
                actions=(
                    ExcelActionSpec("导入/导出", "personnel.excel_operator_calendar_page", "primary"),
                    ExcelActionSpec("导出当前个人日历", "personnel.excel_operator_calendar_export", "secondary"),
                ),
            ),
        )
    )


def scheduler_batch_excel_cards() -> List[Dict[str, object]]:
    return _resolve_cards(
        (
            ExcelCardSpec(
                title="批次信息",
                desc="批量维护批次号、图号、数量、交期、优先级、齐套状态；确认导入时可自动生成或重建批次工序。",
                actions=(
                    ExcelActionSpec("导入/导出", "scheduler.excel_batches_page", "primary"),
                    ExcelActionSpec("导出当前批次", "scheduler.excel_batches_export", "secondary"),
                ),
            ),
        )
    )

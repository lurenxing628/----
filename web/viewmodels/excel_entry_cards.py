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
                title="批量维护路线文字",
                desc="把图号、名称和路线文字从 Excel 导入，系统会生成零件工序清单。",
                actions=(
                    ExcelActionSpec("导入/导出路线", "process.excel_routes_page", "primary"),
                    ExcelActionSpec("导出当前路线", "process.excel_routes_export", "secondary"),
                ),
            ),
            ExcelCardSpec(
                title="批量维护工序工时",
                desc="维护自制工序的换型时间和单件工时；可选择只补空工时。",
                actions=(
                    ExcelActionSpec("导入/导出工时", "process.excel_part_op_hours_page", "primary"),
                    ExcelActionSpec("导出当前工时", "process.excel_part_op_hours_export", "secondary"),
                ),
            ),
            ExcelCardSpec(
                title="导出工序清单",
                desc="导出当前零件工序、归属、供应商和外协周期，用于复核。",
                actions=(
                    ExcelActionSpec("导出工序清单", "process.excel_part_ops_export", "secondary"),
                ),
            ),
        )
    )


def process_op_type_excel_cards() -> List[Dict[str, object]]:
    return _resolve_cards(
        (
            ExcelCardSpec(
                title="批量维护工种",
                desc="维护工种编号、名称和自制/外协归属，供路线生成工序时使用。",
                actions=(
                    ExcelActionSpec("导入/导出工种", "process.excel_op_type_page", "primary"),
                    ExcelActionSpec("导出当前工种", "process.excel_op_type_export", "secondary"),
                ),
            ),
        )
    )


def process_supplier_excel_cards() -> List[Dict[str, object]]:
    return _resolve_cards(
        (
            ExcelCardSpec(
                title="批量维护供应商",
                desc="维护外协供应商、默认周期、状态和对应工种。",
                actions=(
                    ExcelActionSpec("导入/导出供应商", "process.excel_supplier_page", "primary"),
                    ExcelActionSpec("导出当前供应商", "process.excel_supplier_export", "secondary"),
                ),
            ),
        )
    )


def equipment_excel_cards() -> List[Dict[str, object]]:
    return _resolve_cards(
        (
            ExcelCardSpec(
                title="批量维护设备",
                desc="批量维护设备编号、设备名称、工种、班组和状态。",
                actions=(
                    ExcelActionSpec("导入/导出设备", "equipment.excel_machine_page", "primary"),
                    ExcelActionSpec("导出当前设备", "equipment.excel_machine_export", "secondary"),
                ),
            ),
            ExcelCardSpec(
                title="批量维护设备人员关系",
                desc="维护每台设备可由哪些人员操作，以及技能等级和主操设备。",
                actions=(
                    ExcelActionSpec("导入/导出关系", "equipment.excel_link_page", "primary"),
                    ExcelActionSpec("导出当前关系", "equipment.excel_link_export", "secondary"),
                ),
            ),
        )
    )


def personnel_excel_cards() -> List[Dict[str, object]]:
    return _resolve_cards(
        (
            ExcelCardSpec(
                title="批量维护人员",
                desc="批量维护工号、姓名、状态、班组和备注。",
                actions=(
                    ExcelActionSpec("导入/导出人员", "personnel.excel_operator_page", "primary"),
                    ExcelActionSpec("导出当前人员", "personnel.excel_operator_export", "secondary"),
                ),
            ),
            ExcelCardSpec(
                title="批量维护人员设备关系",
                desc="维护每个人员可以操作哪些设备，以及技能等级和主操设备。",
                actions=(
                    ExcelActionSpec("导入/导出关系", "personnel.excel_link_page", "primary"),
                    ExcelActionSpec("导出当前关系", "personnel.excel_link_export", "secondary"),
                ),
            ),
            ExcelCardSpec(
                title="批量维护个人日历",
                desc="维护请假、加班、轮班等个人工作日历。",
                actions=(
                    ExcelActionSpec("导入/导出个人日历", "personnel.excel_operator_calendar_page", "primary"),
                    ExcelActionSpec("导出当前个人日历", "personnel.excel_operator_calendar_export", "secondary"),
                ),
            ),
        )
    )


def scheduler_batch_excel_cards() -> List[Dict[str, object]]:
    return _resolve_cards(
        (
            ExcelCardSpec(
                title="批量维护批次",
                desc="适合 Excel 下发计划、整批新增或更新批次；导入后可自动生成批次工序。",
                actions=(
                    ExcelActionSpec("导入/导出批次", "scheduler.excel_batches_page", "primary"),
                    ExcelActionSpec("导出当前批次", "scheduler.excel_batches_export", "secondary"),
                ),
            ),
        )
    )

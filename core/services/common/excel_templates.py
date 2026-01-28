from __future__ import annotations

import os
from typing import Any, Dict, List, Sequence

import openpyxl


def _write_xlsx(path: str, headers: Sequence[str], sample_rows: Sequence[Sequence[Any]] = ()) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(list(headers))
    for r in sample_rows:
        ws.append(list(r))
    wb.save(path)


def get_default_templates() -> List[Dict[str, Any]]:
    """
    返回需要交付的 Excel 模板清单（文件名 + 表头 + 示例行）。

    说明：
    - 这些模板与各模块的“下载模板”接口保持一致（列名为中文）。
    - 即便某些模块（如批次/日历）尚未在 Phase0~5 提供页面/接口，也可先把模板交付到目录中，
      便于后续直接复用，减少再回读开发文档的成本。
    """
    return [
        # 人员
        {
            "filename": "人员基本信息.xlsx",
            "headers": ["工号", "姓名", "状态", "备注"],
            "sample_rows": [["OP001", "张三", "active", "示例备注"]],
        },
        {
            "filename": "人员设备关联.xlsx",
            "headers": ["工号", "设备编号", "技能等级", "主操设备"],
            "sample_rows": [["OP001", "CNC-01", "normal", "yes"]],
        },
        # 设备
        {
            "filename": "设备信息.xlsx",
            "headers": ["设备编号", "设备名称", "工种", "状态"],
            "sample_rows": [["CNC-01", "数控车床1", "数车", "active"]],
        },
        {
            "filename": "设备人员关联.xlsx",
            "headers": ["设备编号", "工号", "技能等级", "主操设备"],
            "sample_rows": [["CNC-01", "OP001", "normal", "yes"]],
        },
        # 工艺
        {
            "filename": "工种配置.xlsx",
            "headers": ["工种ID", "工种名称", "归属"],
            "sample_rows": [["OT001", "数车", "internal"], ["OT002", "标印", "external"]],
        },
        {
            "filename": "供应商配置.xlsx",
            "headers": ["供应商ID", "名称", "对应工种", "默认周期"],
            "sample_rows": [["S001", "外协-标印厂", "标印", 1]],
        },
        {
            "filename": "零件工艺路线.xlsx",
            "headers": ["图号", "名称", "工艺路线字符串"],
            "sample_rows": [["A1234", "壳体-大", "5数铣10钳20数车35标印40总检45表处理"]],
        },
        # 排产（后续阶段会接入接口/页面；模板先交付）
        {
            "filename": "批次信息.xlsx",
            # 对齐路由 `web/routes/scheduler_excel_batches.py` 的兜底模板与导入字段（含齐套日期）
            "headers": ["批次号", "图号", "数量", "交期", "优先级", "齐套", "齐套日期", "备注"],
            "sample_rows": [["B001", "A1234", 50, "2026-01-25", "urgent", "yes", "2026-01-24", "示例"]],
        },
        {
            "filename": "工作日历.xlsx",
            "headers": ["日期", "类型", "可用工时", "效率", "允许普通件", "允许急件", "说明"],
            "sample_rows": [["2026-01-21", "workday", 8, 1.0, "yes", "yes", "示例"]],
        },
    ]


def ensure_excel_templates(template_dir: str) -> Dict[str, Any]:
    """
    确保 templates_excel 目录下存在所有交付模板文件。
    - 若文件存在则不覆盖（避免用户手工修改被覆盖）
    - 若目录为空/缺失，则补齐
    """
    template_dir = os.path.abspath(template_dir or "templates_excel")
    os.makedirs(template_dir, exist_ok=True)

    created: List[str] = []
    skipped: List[str] = []

    for t in get_default_templates():
        filename = t["filename"]
        path = os.path.join(template_dir, filename)
        if os.path.exists(path):
            skipped.append(filename)
            continue
        _write_xlsx(path, headers=t["headers"], sample_rows=t.get("sample_rows") or [])
        created.append(filename)

    return {"template_dir": template_dir, "created": created, "skipped": skipped}


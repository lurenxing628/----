"""单元 Excel 转换的逐条诊断落账：把 parser 侧留在 StepRecord/PartContext 上的退化痕迹
（坏单元格、旧格式兼容行、工艺路线丢弃片段），以及工作簿/表头级的解析留痕
（多工作表提示、被丢弃的设备列块、图号取值畸变）统一记进 DegradationCollector + samples。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from core.services.common.degradation import DegradationCollector

from .parser import PartContext, StepRecord
from .template_validation import record_diagnostic


def record_step_record_diagnostics(
    *,
    ctx: PartContext,
    rec: StepRecord,
    collector: DegradationCollector,
    samples: Dict[str, List[Any]],
) -> None:
    for issue in list(getattr(rec, "diagnostics", None) or []):
        if not isinstance(issue, dict):
            continue
        record_diagnostic(
            collector,
            samples,
            code=str(issue.get("code") or "invalid_unit_excel_cell"),
            scope="unit_excel.step_record",
            field=str(issue.get("field") or ""),
            message=str(issue.get("message") or "单元 Excel 中有无法识别的单元格，系统已按可确认内容继续转换。"),
            sample={
                "part_no": ctx.part_no,
                "machine_id": rec.machine_id,
                "step_text": rec.step_text,
                "row_num": int(issue.get("row_num") or getattr(rec, "row_num", 0) or 0),
                "field": issue.get("field"),
                "raw_value": issue.get("raw_value"),
            },
        )


def record_compatible_row_diagnostic(
    *,
    ctx: PartContext,
    rec: StepRecord,
    collector: DegradationCollector,
    samples: Dict[str, List[Any]],
) -> None:
    if not rec.step_text or (rec.has_step_code and rec.operators):
        return
    record_diagnostic(
        collector,
        samples,
        code="compatible_row",
        scope="unit_excel.step_record",
        field="step_text",
        message="发现旧格式行，系统已按旧文件的写法识别并继续转换。",
        sample={
            "part_no": ctx.part_no,
            "machine_id": rec.machine_id,
            "step_text": rec.step_text,
            "has_step_code": bool(rec.has_step_code),
            "operator_count": int(len(rec.operators or [])),
        },
    )


# parse 级诊断的样本负载键：不同 code 只带自己相关的键（多工作表带 sheet 名，列块带列范围/表头等）。
_PARSE_SAMPLE_KEYS = ("row_num", "raw_value", "used_sheet", "sheet_names", "columns", "headers", "values")


def record_parse_diagnostics(
    *,
    parse_diagnostics: Optional[Iterable[Dict[str, Any]]],
    collector: DegradationCollector,
    samples: Dict[str, List[Any]],
) -> None:
    """把 parser 侧工作簿/表头/图号级的退化留痕逐条聚合进 diagnostics.counters/samples。"""
    for issue in list(parse_diagnostics or []):
        if not isinstance(issue, dict):
            continue
        sample: Dict[str, Any] = {}
        for key in _PARSE_SAMPLE_KEYS:
            value = issue.get(key)
            if value is not None:
                sample[key] = value
        record_diagnostic(
            collector,
            samples,
            code=str(issue.get("code") or "unit_excel_parse_degraded"),
            scope=str(issue.get("scope") or "unit_excel.parse"),
            field=str(issue.get("field") or ""),
            message=str(issue.get("message") or "单元 Excel 解析阶段发现退化，系统已按可确认内容继续转换。"),
            sample=sample,
        )


def record_route_diagnostics(
    *,
    ctx: PartContext,
    collector: DegradationCollector,
    samples: Dict[str, List[Any]],
) -> None:
    for issue in list(getattr(ctx, "route_diagnostics", None) or []):
        if not isinstance(issue, dict):
            continue
        sample: Dict[str, Any] = {"part_no": ctx.part_no}
        for key in ("row_num", "raw_value", "segment", "seq", "kept_name", "dropped_name"):
            value = issue.get(key)
            if value is not None:
                sample[key] = value
        record_diagnostic(
            collector,
            samples,
            code=str(issue.get("code") or "route_segment_dropped"),
            scope="unit_excel.route",
            field=str(issue.get("field") or "工艺路线"),
            message=str(issue.get("message") or "工艺路线中有无法识别的片段，系统已跳过，请核对工艺路线写法。"),
            sample=sample,
        )

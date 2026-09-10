"""单元 Excel 单元格取值与逐格诊断：文本化、正数工时解析、工序号解析，以及
Excel 自动类型转换（工序号/图号被存成日期、图号被存成数字）造成的取值畸变识别。
约定：丢弃或降级必须产出诊断 dict 留痕，由转换链聚合进 diagnostics.counters/samples。"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

_STEP_WITH_CODE_RE = re.compile(r"^(\d{1,3})-([0-9A-Za-z]+)")
_STEP_SEQ_ONLY_RE = re.compile(r"^(\d{1,3})")


def to_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return str(v).strip()


def build_cell_diagnostic(
    *,
    code: str,
    field: str,
    message: str,
    row_num: int,
    raw_value: Any,
    error: Optional[BaseException] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "code": code,
        "field": field,
        "message": message,
        "row_num": int(row_num or 0),
        "raw_value": str(raw_value)[:120],
    }
    if error is not None:
        out["error_type"] = type(error).__name__
    return out


def step_cell_date_issue(raw_value: Any, *, row_num: int) -> Optional[Dict[str, Any]]:
    """工序号单元格被 Excel 自动存成日期（如"10-1"变成 2026-10-01）时产出诊断。

    不做任何"猜测恢复"：调用方必须按无法识别的工序号处理（seq=None），
    否则日期字符串会被截出错误工序号（如 202）并误判内外协。"""
    if not isinstance(raw_value, (datetime, date)):
        return None
    return build_cell_diagnostic(
        code="step_cell_date_coerced",
        field="工序号",
        message="工序号列被 Excel 存成了日期格式，系统无法识别该工序号；请把该列改为文本格式后重新导出。",
        row_num=row_num,
        raw_value=raw_value,
    )


def part_no_cell_coercion_issue(raw_value: Any, *, row_num: int) -> Optional[Dict[str, Any]]:
    """图号单元格被 Excel 自动存成日期/小数（含科学计数法）时产出诊断。

    转换仍按文本化后的值继续（避免把整行数据错挂到上一个图号），但畸变必须留痕。"""
    issue: Optional[Dict[str, Any]] = None
    if isinstance(raw_value, (datetime, date)):
        issue = build_cell_diagnostic(
            code="part_no_cell_date_coerced",
            field="图号",
            message="图号列被 Excel 存成了日期格式，转换出的图号可能不正确；请把该列改为文本格式后重新导出。",
            row_num=row_num,
            raw_value=raw_value,
        )
    elif isinstance(raw_value, float):
        issue = build_cell_diagnostic(
            code="part_no_cell_number_coerced",
            field="图号",
            message="图号列被 Excel 存成了数字格式（可能出现小数点或科学计数法），转换出的图号可能不正确；请把该列改为文本格式后重新导出。",
            row_num=row_num,
            raw_value=raw_value,
        )
    if issue is not None:
        issue["scope"] = "unit_excel.part"
    return issue


def parse_step_seq(step_text: str) -> Tuple[Optional[int], bool]:
    seq, has_step_code, _issue = parse_step_seq_detail(step_text, row_num=0)
    return seq, has_step_code


def parse_step_seq_detail(step_text: str, *, row_num: int) -> Tuple[Optional[int], bool, Optional[Dict[str, Any]]]:
    s = (step_text or "").strip()
    if not s:
        return None, False, None
    m = _STEP_WITH_CODE_RE.match(s)
    if m:
        try:
            return int(m.group(1)), True, None
        except Exception as exc:
            return None, True, build_cell_diagnostic(
                code="invalid_step_seq",
                field="工序号",
                message="工序号无法识别，系统已跳过这条工序号。",
                row_num=row_num,
                raw_value=step_text,
                error=exc,
            )
    m2 = _STEP_SEQ_ONLY_RE.match(s)
    if m2:
        try:
            return int(m2.group(1)), False, None
        except Exception as exc:
            return None, False, build_cell_diagnostic(
                code="invalid_step_seq",
                field="工序号",
                message="工序号无法识别，系统已跳过这条工序号。",
                row_num=row_num,
                raw_value=step_text,
                error=exc,
            )
    return None, False, build_cell_diagnostic(
        code="invalid_step_seq",
        field="工序号",
        message="工序号无法识别，系统已按可确认内容继续转换。",
        row_num=row_num,
        raw_value=step_text,
    )


def parse_positive_float(v: Any) -> Tuple[Optional[float], Optional[str]]:
    if v is None:
        return None, None
    if isinstance(v, bool):
        return None, "invalid_number"
    if isinstance(v, (int, float)):
        try:
            fv = float(v)
        except Exception:
            return None, "invalid_number"
        if not math.isfinite(fv):
            return None, "non_finite_number"
        return (fv, None) if fv > 0 else (None, "number_below_minimum")
    s = str(v).strip()
    if not s:
        return None, None
    s = s.replace(",", "")
    try:
        fv = float(s)
    except Exception:
        return None, "invalid_number"
    if not math.isfinite(fv):
        return None, "non_finite_number"
    return (fv, None) if fv > 0 else (None, "number_below_minimum")


def to_float(v: Any) -> Optional[float]:
    return parse_positive_float(v)[0]


def float_issue_message(issue_code: str, field: str) -> str:
    if issue_code == "non_finite_number":
        return f"{field} 不是有限数字，系统已忽略该单元格。"
    if issue_code == "number_below_minimum":
        return f"{field} 必须大于 0，系统已忽略该单元格。"
    return f"{field} 不是有效数字，系统已忽略该单元格。"


def to_float_with_diagnostic(
    v: Any,
    *,
    row_num: int,
    field: str,
    diagnostics: List[Dict[str, Any]],
) -> Optional[float]:
    value, issue_code = parse_positive_float(v)
    if issue_code is not None:
        diagnostics.append(
            build_cell_diagnostic(
                code=issue_code,
                field=field,
                message=float_issue_message(issue_code, field),
                row_num=row_num,
                raw_value=v,
            )
        )
    return value

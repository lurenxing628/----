from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

DataGapReason = Dict[str, str]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _looks_like_date(value: Any) -> bool:
    """整串匹配判断是否为可解析日期/时间（兼容 `/`、T、纯日期/分钟/秒级）。"""
    text = str(value or "").strip().replace("/", "-").replace("T", " ")
    if not text:
        return False
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            datetime.strptime(text, fmt)
            return True
        except ValueError:
            continue
    return False


def _has_parseable_range(plan_time_span: Dict[str, Any]) -> bool:
    return _looks_like_date(plan_time_span.get("start_time")) and _looks_like_date(plan_time_span.get("end_time"))


def _data_gap_reason(title: str, impact: str, evidence: str) -> DataGapReason:
    return {"title": title, "impact": impact, "evidence": evidence}


def _history_gap_reason(
    *,
    latest_history: Any,
    context: Dict[str, Any],
    parse_failed: bool,
    parse_error: str,
) -> Optional[DataGapReason]:
    if latest_history is None:
        return _data_gap_reason(
            "基础数据还不够",
            "还没有排产版本，首页暂时不能生成排产风险、日期范围和现场复盘入口。",
            "数据库里还没有排产历史。",
        )
    identity_error = _text(context.get("plan_identity_error"))
    if not identity_error:
        return None
    evidence = identity_error
    if parse_failed:
        evidence = f"{evidence}；当前排产摘要读取失败：{parse_error or '当前排产摘要结构无法安全解析。'}"
    return _data_gap_reason(
        "当前请求不可用",
        "首页已回到可用方案显示，避免把无效链接当作真实方案继续处理。",
        evidence,
    )


def _summary_gap_reason(
    *,
    latest_summary: Optional[Dict[str, Any]],
    parse_failed: bool,
    parse_error: str,
) -> Optional[DataGapReason]:
    if parse_failed:
        return _data_gap_reason(
            "当前排产摘要读取失败",
            "部分风险只能显示基础信息，建议先打开排产分析核对这版结果。",
            parse_error or "当前排产摘要结构无法安全解析。",
        )
    # 与 _has_current_summary（dashboard_workbench.py：isinstance dict and bool(summary) and not parse_failed）
    # 同口径：空 dict {} / 非 dict 也是「摘要不可用」，须进数据缺口——否则 6 格里超期/现场/方案都显
    # 「数据不足」而「基础数据」却显「完整」，自相矛盾。
    if not isinstance(latest_summary, dict) or not latest_summary:
        return _data_gap_reason(
            "当前排产摘要为空",
            "首页只能显示版本和基础统计，暂时不能判断方案、负荷和超期细节。",
            "当前查看方案没有可用的首页摘要内容。",
        )
    return None


def _plan_gap_reason(
    *,
    plan_time_span: Optional[Dict[str, Any]],
    plan_time_span_load_error: str,
    today_rows_load_error: str,
    execution_facts_load_error: str,
) -> Optional[DataGapReason]:
    if _text(plan_time_span_load_error):
        return _data_gap_reason(
            "计划日期范围暂时读不到",
            "需要日期的甘特、资源派工和报表入口会先禁用，避免把读取失败误当成没有日期。",
            _text(plan_time_span_load_error),
        )
    if not isinstance(plan_time_span, dict) or not _has_parseable_range(plan_time_span):
        # 非 dict 或 start/end 无法解析（坏日期范围）都按「缺少日期范围」处理——不让坏日期 dict
        # 通过 isinstance 检查后冒充「基础数据完整」、把需要日期的入口误放行。
        return _data_gap_reason(
            "当前计划缺少日期范围",
            "需要日期的甘特、资源派工和报表入口会先禁用，避免跳到不确定的范围。",
            "当前版本没有读到有效的计划开始和结束时间。",
        )
    if _text(today_rows_load_error):
        return _data_gap_reason(
            "今日计划暂时读不到",
            "首页暂时不能判断今天哪些任务现场情况待确认，避免把读取失败误当成没有待确认。",
            _text(today_rows_load_error),
        )
    if _text(execution_facts_load_error):
        return _data_gap_reason(
            "现场情况暂时读不到",
            "首页暂时不能判断哪些任务现场情况待确认，避免把读取失败误当成现场没有反馈。",
            _text(execution_facts_load_error),
        )
    return None


def dashboard_data_gap_reason(
    *,
    latest_history: Any,
    context: Dict[str, Any],
    latest_summary: Optional[Dict[str, Any]],
    latest_summary_parse_state: Optional[Dict[str, Any]],
    plan_time_span: Optional[Dict[str, Any]],
    plan_time_span_load_error: str,
    today_rows_load_error: str,
    execution_facts_load_error: str,
) -> Optional[DataGapReason]:
    parse_state = latest_summary_parse_state if isinstance(latest_summary_parse_state, dict) else {}
    parse_failed = bool(parse_state.get("parse_failed"))
    parse_error = _text(parse_state.get("user_message"))
    return (
        _history_gap_reason(
            latest_history=latest_history,
            context=context,
            parse_failed=parse_failed,
            parse_error=parse_error,
        )
        or _summary_gap_reason(
            latest_summary=latest_summary,
            parse_failed=parse_failed,
            parse_error=parse_error,
        )
        or _plan_gap_reason(
            plan_time_span=plan_time_span,
            plan_time_span_load_error=plan_time_span_load_error,
            today_rows_load_error=today_rows_load_error,
            execution_facts_load_error=execution_facts_load_error,
        )
    )


__all__ = ["dashboard_data_gap_reason"]

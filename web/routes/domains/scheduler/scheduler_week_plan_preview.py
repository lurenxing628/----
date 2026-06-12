"""周计划页预览态装配（fusion-week-plan-enrich）：空周提示升级 + 预览行状态。

从 scheduler_week_plan.py 拆出（该文件触及 500 行红线）；纯装配无路由。
"""

from __future__ import annotations

from flask import current_app

from core.services.scheduler.schedule_result_view_range import get_plan_time_span_dates
from web.viewmodels.scheduler_workbench_links import build_workbench_link, build_workbench_plan_context


def week_plan_span_jump(services, data) -> dict:
    """空周升级（fusion-week-plan-enrich）：版本有计划行时告知区间并给跳转链接。

    span 读取是锦上添花——per-call 宽 catch + logger.warning 留痕，
    失败回落现有空文案，不把升级变成新故障点；无计划行（失败/模拟）零跳转。
    """
    version = data.get("version")
    if not version:
        return {}
    try:
        # attach_plan_metadata 写入的键名是 plan_role_resolution（含 selected_role/
        # scenario_id）——读错键会把非正式方案/模拟预览误当 adopted（Codex 阻塞修复）
        raw_meta = data.get("plan_role_resolution")
        plan_meta = raw_meta if isinstance(raw_meta, dict) else {}
        role = str(plan_meta.get("selected_role") or "adopted")
        scenario = plan_meta.get("scenario_id")
        span = get_plan_time_span_dates(services.schedule_plan_query_service, int(version), role, scenario)
        if not span:
            return {}
        context = build_workbench_plan_context(
            version=int(version), plan_role=role, scenario_id=scenario,
            date_from=span["start_date"], date_to=span["end_date"],
        )
        link = build_workbench_link(context, "week_plan", label="跳到计划区间")
        return {"span": span, "jump_link": link}
    except Exception as exc:
        current_app.logger.warning("周计划空周区间升级读取失败（version=%s）：%s", version, exc)
        return {}


def build_week_plan_preview_state(data, *, span_jump=None):
    rows = data.get("rows") or []
    degradation_counters = data.get("degradation_counters") or {}
    bad_time_skipped = int(degradation_counters.get("bad_time_row_skipped") or 0)
    degradation_message = ""
    if bad_time_skipped > 0:
        degradation_message = f"已过滤 {bad_time_skipped} 条开始或结束时间写法不对的排程记录。"
    empty_message = "暂无数据（该周/该版本没有排程记录）。"
    empty_jump_link = None
    if not rows and span_jump:
        span = span_jump["span"]
        empty_message = f"该周没有排程；这个版本的计划在 {span['start_date']} ～ {span['end_date']}。"
        empty_jump_link = span_jump.get("jump_link")
    if not rows and str(data.get("empty_reason") or "") == "all_rows_filtered_by_invalid_time":
        # 坏时间过滤态：问题是数据不是选错周——跳转链接会误导，清掉
        empty_jump_link = None
        if bad_time_skipped > 0:
            empty_message = (
                f"已过滤 {bad_time_skipped} 条开始或结束时间写法不对的排程记录。"
                "当前区间没有可显示排程，请到系统管理里的排产历史查看这次排产的详细提醒。"
            )
        else:
            empty_message = "当前区间的排程开始或结束时间写法不对，已全部过滤，请到系统管理里的排产历史查看这次排产的详细提醒。"
    return {
        "rows": rows,
        "preview_rows": rows[:50],
        "degradation_message": degradation_message,
        "empty_message": empty_message,
        "empty_jump_link": empty_jump_link,
    }


__all__ = ["build_week_plan_preview_state", "week_plan_span_jump"]

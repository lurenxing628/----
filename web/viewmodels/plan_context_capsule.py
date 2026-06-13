"""壳层计划上下文胶囊 builder（fusion-plan-context-capsule，契约 4.2）。

胶囊是 top-header 常驻的一行计划上下文（版本 · 方案身份 · 生成时间 · 策略 ·
数据范围），全站统一渲染。只消费 build_workbench_plan_context 输出的 *_label
公开字段——不显示 plan_role/scenario_id raw 值；缺字段显示「-」。

胶囊是上下文回显不是数据查询入口：context 无 version 返回 None（基础数据页
零渲染）；URL fallback 进来的页面 generated_at/strategy 为「-」，不查库补。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_plan_context_capsule(context: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """从工作台导航 context 取胶囊五字段；无 version 返回 None（页面零渲染）。"""
    if not _text(context.get("version")):
        return None
    date_from = _text(context.get("date_from"))
    date_to = _text(context.get("date_to"))
    return {
        "version_label": _text(context.get("version_label")) or "-",
        "plan_role_label": _text(context.get("plan_role_label")) or "-",
        "generated_at_label": _text(context.get("generated_at_label")) or "-",
        "strategy_label": _text(context.get("strategy_label")) or "-",
        "date_range_label": f"{date_from} ～ {date_to}" if date_from and date_to else "-",
    }


def history_row_capsule_fields(rows: Any, version: Any) -> Dict[str, Any]:
    """从 decorated 历史行列表按 version 取喂参字段；查不到返回空 dict。

    查不到（如 limit-30 外的旧版本号）→ 胶囊该两项显示「-」——诚实降级是
    有意行为不是漏查：胶囊是上下文回显，不为它另发查询。
    """
    try:
        version_int = int(version)
    except (TypeError, ValueError):
        return {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        try:
            row_version = int(_text(row.get("version")))
        except (TypeError, ValueError):
            continue
        if row_version == version_int:
            return {"generated_at": row.get("schedule_time"), "strategy": row.get("strategy")}
    return {}


__all__: List[str] = ["build_plan_context_capsule", "history_row_capsule_fields"]

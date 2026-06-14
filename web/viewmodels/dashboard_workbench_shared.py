"""首页值班台跨职责共享纯工具（fusion-due-soon-alert 微重构第 1 步，只搬不改行为）。

被 dashboard_workbench.py（编排 / build_summary）与 dashboard_workbench_todos.py（todo builders）共用，
且被 test_dashboard_workbench_contract.py 直接 import。本模块不 import 上述两者——单向依赖、无循环。
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, Optional


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(default)  # bool 不是计数：int(True)==1 会把脏 True 冒充「1 套候选」，按类型混入剔除
    try:
        return int(value or default)
    except (TypeError, ValueError, OverflowError):
        return int(default)  # OverflowError：int(float('inf')) 等脏值不得冒泡崩溃首页


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None  # NaN/±Inf 不是可用数值，按脏值剔除（否则 nan<0 恒 False 会漏过冒充正常负荷）
    return number


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = _text(value).replace("/", "-").replace("T", " ").replace("：", ":")
    # 整串匹配（不截前缀）：坏后缀（'...08:00:00xyz'）应解析失败而非被截断成合法日期
    # 静默当成正常时间（与 dashboard_cockpit_hero._parse_dt 同口径）。
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError("datetime value is required")


def _datetime_label(value: Any) -> str:
    if isinstance(value, datetime):
        return f"{value.year}年{value.month}月{value.day}日 {value.hour:02d}:{value.minute:02d}"
    text = _text(value)
    if not text:
        return "-"
    try:
        parsed = _parse_datetime(text)
    except ValueError:
        return text
    return f"{parsed.year}年{parsed.month}月{parsed.day}日 {parsed.hour:02d}:{parsed.minute:02d}"


def _machine_util_ratio(latest_summary: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(latest_summary, dict):
        return None
    algo = latest_summary.get("algo")
    if not isinstance(algo, dict):
        return None
    metrics = algo.get("metrics")
    if not isinstance(metrics, dict):
        return None
    if isinstance(metrics.get("machine_util_avg"), bool):
        return None
    raw = _safe_float(metrics.get("machine_util_avg"))
    if raw is None or raw < 0:
        return None
    if raw > 1:
        if raw <= 100:
            return raw / 100.0
        return None
    return raw


def _candidate_comparison(summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(summary, dict):
        return None
    algo = summary.get("algo")
    if not isinstance(algo, dict):
        return None
    comparison = algo.get("candidate_comparison")
    if not isinstance(comparison, dict):
        return None
    # 与分析页同口径（scheduler_analysis_candidate_helpers._candidate_comparison_summary）：
    # 候选生成被显式关闭（enabled=False）时视为无候选，首页不误报「方案待确认」。
    if comparison.get("enabled") is False:
        return None
    return comparison


__all__ = [
    "_text",
    "_safe_int",
    "_safe_float",
    "_parse_datetime",
    "_datetime_label",
    "_machine_util_ratio",
    "_candidate_comparison",
]

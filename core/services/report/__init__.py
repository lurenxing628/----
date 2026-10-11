"""
报表引擎（ReportEngine）。

V1 MVP：
- 超期清单
- 设备/人员负荷与利用率
- 停机影响统计
"""

from __future__ import annotations

from typing import TYPE_CHECKING


def __getattr__(name: str):
    if name == "ReportEngine":
        from .report_engine import ReportEngine

        globals()[name] = ReportEngine
        return ReportEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["ReportEngine"]

if TYPE_CHECKING:
    from .report_engine import ReportEngine


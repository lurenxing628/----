"""Presentation-only navigation; route identities survive sidebar consolidation."""

VIEW_TITLES = {
    "dashboard": "值班台", "process": "基础资料", "batches": "批次管理", "run": "执行排产",
    "analysis": "选择排产方案", "gantt": "计划甘特", "delay": "交付风险",
    "field": "现场记录", "fieldgantt": "现场实际甘特", "review": "执行复盘",
    "reports": "报表中心", "calib": "工时定额校准", "basedata": "资料总览", "system": "系统管理",
    "trial": "试调排产方案",
}

NAV_GROUPS = (
    ("值班台", (("dashboard", "home"),)),
    ("数据准备", (("process", "database"), ("basedata", "grid"), ("batches", "box"))),
    ("排产", (("run", "play"), ("analysis", "chart"), ("trial", "square-pen"))),
    ("现场", (("field", "clipboard"), ("fieldgantt", "gantt"))),
    ("统计分析", (("reports", "file"), ("calib", "scale"))),
    ("系统", (("system", "settings"),)),
)

VIEW_ALIASES = {"gantt": "analysis", "delay": "analysis", "review": "reports"}


def navigation_groups():
    """Create independent JSON rows, with labels from the public view titles."""
    return [{"title": title, "items": [{"id": view, "label": VIEW_TITLES[view], "icon": icon}
                                       for view, icon in items]} for title, items in NAV_GROUPS]

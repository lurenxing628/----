"""页面级“本页说明”注册表：以工作台视图 id 为键，指向整本说明书里的章节。

2026-09-21 起顶栏「帮助」带 ``page=<视图 id>`` 打开说明书页时，``manual_page`` 用这里的
``heading`` 在 ``static/docs/scheduler_manual.md`` 里找到同名标题，把该标题到下一个同级或更高级
标题之间的正文当作“本页说明”。``related`` 列出可顺手查看的相邻视图，同样用视图 id。

这里只放纯数据：视图 id 与 ``web/routes/workbench/navigation_metadata.VIEW_TITLES`` 一一对应，
标题文字必须和说明书里的标题逐字相同（测试会锁住这两条约束）。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

VIEW_MANUALS: Dict[str, Dict[str, Any]] = {
    "dashboard": {
        "title": "值班台",
        "heading": "值班台怎么看",
        "summary": "先看 7 张卡和「需要关注」清单，再决定去哪个页面处理。",
        "related": ("batches", "run", "analysis"),
    },
    "process": {
        "title": "基础资料",
        "heading": "5. 数据准备：排产前必须做的事",
        "summary": "按产能链维护工艺、物料、工种、设备、人员、供应商和工作日历，排产前先把这些资料补齐。",
        "related": ("basedata", "batches"),
    },
    "basedata": {
        "title": "资料总览",
        "heading": "5.8 资料总览",
        "summary": "一页看完所有基础资料的待维护项，点「维护」直接跳到对应资料。",
        "related": ("process", "batches"),
    },
    "batches": {
        "title": "批次管理",
        "heading": "6.1 批次管理",
        "summary": "新增、导入、筛选批次，进批次详情补设备、人员、工时和外协周期。",
        "related": ("process", "run"),
    },
    "run": {
        "title": "执行排产",
        "heading": "6.2 执行排产",
        "summary": "选批次和日期、做排产检查、生成候选方案，再在候选方案页采用为正式计划。",
        "related": ("batches", "analysis", "trial"),
    },
    "analysis": {
        "title": "选择排产方案",
        "heading": "6.3 选择排产方案",
        "summary": "选一份正式计划、候选方案或试调方案，看范围内安排、关联批次和预计超期。",
        "related": ("gantt", "delay", "trial"),
    },
    "gantt": {
        "title": "计划甘特",
        "heading": "6.4 计划甘特",
        "summary": "按设备、人员或批次看计划安排，点任务看详情、前后序和初始计划对照。",
        "related": ("analysis", "delay", "field"),
    },
    "delay": {
        "title": "交付风险",
        "heading": "6.5 交付风险",
        "summary": "按批次看预计超期、未排工序，再看资源负荷和资源班表。",
        "related": ("analysis", "gantt", "run"),
    },
    "trial": {
        "title": "试调排产方案",
        "heading": "6.6 试调排产方案",
        "summary": "从正式计划或候选方案新增草稿，逐道调整设备、人员、开工时间，保存后再采用。",
        "related": ("analysis", "run", "gantt"),
    },
    "field": {
        "title": "现场记录",
        "heading": "9.1 现场记录",
        "summary": "按工序登记本次报工、补齐、更正或撤销，也能用报工文件整批导入导出。",
        "related": ("fieldgantt", "reports", "gantt"),
    },
    "fieldgantt": {
        "title": "现场实际甘特",
        "heading": "9.2 现场实际甘特",
        "summary": "按设备、人员或批次看实际报工的时间分布，和计划对照。",
        "related": ("field", "gantt", "reports"),
    },
    "reports": {
        "title": "报表中心",
        "heading": "10.1 报表中心",
        "summary": "按计划完工日期范围看工序完成情况、报工记录、设备和人员工时、数据完整性，可导出。",
        "related": ("review", "calib", "field"),
    },
    "review": {
        "title": "执行复盘",
        "heading": "10.2 执行复盘",
        "summary": "看计划与实际累计完工、整道完工偏差和实际资源工时的图表。",
        "related": ("reports", "calib"),
    },
    "calib": {
        "title": "工时定额校准",
        "heading": "10.4 工时定额校准",
        "summary": "用已确认的整道完工记录给单件工时提建议，核对后采用并锁定模板定额。",
        "related": ("reports", "process"),
    },
    "system": {
        "title": "系统管理",
        "heading": "11. 系统管理",
        "summary": "本机备份恢复、运行日志、自动维护配置和页面偏好。",
        "related": ("dashboard",),
    },
}

MANUAL_VIEW_IDS: Tuple[str, ...] = tuple(VIEW_MANUALS)


def manual_entry(view_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """按视图 id 取“本页说明”登记；未登记或空值返回 None，不做别名猜测。"""
    key = str(view_id or "").strip()
    if not key:
        return None
    entry = VIEW_MANUALS.get(key)
    if entry is None:
        return None
    return dict(entry, view=key)


# 旧路由层的端点键映射已随旧页面退役（2026-09-21）。下面三个名字只为 ``web/viewmodels/page_manuals.py``
# 和 ``web/manual_src_security.py`` 的既有导入不断，内容一律为空；新代码不要再往里加条目。
ENDPOINT_TO_MANUAL_ID: Dict[str, str] = {}
MANUAL_ENTRY_ENDPOINTS: Dict[str, str] = {}
ENDPOINT_OVERRIDES: Dict[str, Dict[str, Any]] = {}

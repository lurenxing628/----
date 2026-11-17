"""Workbench navigation metadata: view titles, sidebar groups and the controlled navigation declaration.

Route identities survive sidebar consolidation (``VIEW_ALIASES``). ``NAVIGATION_RULES`` is pure data sent to the
browser in the boot config; ``navigation_boot.read_navigation`` (explicit ``?nav=``) and ``WorkbenchNavigation``
(``history.state``) each interpret it once, so both admission points read the same rules.
"""

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


# 受控导航声明。每个页面两种入口：
# - url：顶层 ?nav= 能不能带非空定位。可定位的键和取值由 navigation_boot 的地址解析器逐页核对（可定位范围表）；
#   为 False 的页面只接受空定位。
# - restore：页面记忆、侧栏恢复和 return_to.context 共用的可恢复状态表，按变体登记，见 _state。
#   return_to 是返回信封 {view, context?}：context 按目标页的 restore 规则递归准入；不带 context
#   表示回去恢复目标页自己记住的状态。取值的领域检查归各页读取方，这里只登记键和键之间的关系。
_RETURN = "return_to"


def _state(fields, *, name=None, when=None, required=(), requires=None, excludes=None):
    """One restorable state variant, always with every key so both interpreters index it directly.

    ``when`` picks the variant: ``{"has": keys}`` holds when any key is present, ``{"is": {key: value}}`` when each
    key equals the value (a list value means one of); ``None`` is the fallback. ``fields`` are the allowed keys,
    ``required`` must be present, ``requires`` maps a key to keys that must come with it and ``excludes`` to keys
    that must not. ``name`` labels the variants a page routes on (plan centre and run page).
    """
    return {"name": name, "when": when, "fields": list(fields), "required": list(required),
            "requires": requires or {}, "excludes": excludes or {}}


# 候选结果、方案对比、候选甘特与受理时正式基准共用一份状态：地址定位键、页面记忆键和后端下钻目标里的键。
_CANDIDATE_FIELDS = (
    "run_ref", "candidate_ref", "reference_candidate_ref", "selected_candidate_ref", "comparison_mode",
    "range_start", "range_end", "batch_ref", "operation_ref", "selected_row_ref", "candidate_tab",
    "comparison_tab", "reference_view", "plan_ref", "resource_view", "resource_kind", "resource_ref",
    "selected_batch_ref", "query", "sort", "order", "detail_queries", "detail_query", "drill_range_adjusted", _RETURN,
)
_PLAN_CENTER = [
    _state(_CANDIDATE_FIELDS, name="candidate", when={"has": ["run_ref", "candidate_ref"]}),
    _state(("source", "history_topic", "history_query", "decision_history_context", _RETURN),
           name="history", when={"is": {"source": "run_history"}}),
    _state(("plan_ref", "range_start", "range_end", "query", "selected_task_ref", "selected_task_side",
            "selected_batch_ref", "projection_tab", "projection_page", "resource_kind", _RETURN), name="plan",
           requires={"selected_task_side": ["selected_task_ref"]}, excludes={"selected_batch_ref": ["selected_task_ref"]}),
]
_REPORT = [_state(("scope", "topic", "table", "selected", "chartsOpen", "catalogOpen", "scroll", "resourceView",
                   "detailView", _RETURN))]
_PART_LOCATE = ("entity_ref", "stage", "template_operation_ref", "template_external_group_ref")

NAVIGATION_RULES = {
    "dashboard": {"url": False, "restore": [
        _state(("scope", "tab", "item_ref", "history_page", "analysis_batch_ref", "comparison"))]},
    "process": {"url": True, "restore": [
        _state(("source", "kind", "month", "date"), when={"is": {"kind": "calendar"}}, required=("source", "kind", "month")),
        _state(("source", "kind", "read_view") + _PART_LOCATE, when={"is": {"kind": "part"}}, required=("source", "kind"),
               excludes={"read_view": list(_PART_LOCATE)}),
        _state(("source", "kind", "category", "entity_ref", "read_view"), when={"is": {"kind": "op_type"}},
               required=("source", "kind", "category"), excludes={"read_view": ["entity_ref"]}),
        _state(("source", "kind", "entity_ref", "read_view"), when={"is": {"kind": ["material", "machine", "operator", "supplier"]}},
               required=("source", "kind"), excludes={"read_view": ["entity_ref"]}),
        _state(("source",)),
    ]},
    "basedata": {"url": False, "restore": [
        _state(("domain", "entity_ref", "read_view"), requires={"domain": ["entity_ref"], "entity_ref": ["domain"]},
               excludes={"read_view": ["domain", "entity_ref"]})]},
    "batches": {"url": True, "restore": [
        _state(("entity_ref", "batch_ref", "focus", "batchIds", "read_view", _RETURN),
               excludes={"read_view": ["entity_ref", "batch_ref", "focus", "batchIds"]})]},
    "run": {"url": True, "restore": [
        _state(_CANDIDATE_FIELDS, name="candidate", when={"has": ["run_ref"]}),
        _state(("batch_refs", "start_date", "end_date", "ready_check", "material_strategy", "missing_resource_policy",
                "completed_policy", "hold_window", "time_budget_seconds", "scope", "entity_ref", _RETURN), name="preflight",
               excludes={"scope": ["batch_refs", "entity_ref"], "entity_ref": ["batch_refs"]}),
    ]},
    "analysis": {"url": True, "restore": _PLAN_CENTER},
    "gantt": {"url": True, "restore": _PLAN_CENTER},
    "delay": {"url": True, "restore": _PLAN_CENTER},
    "field": {"url": False, "restore": [
        _state(("plan_ref", "scope", "table", "task_ref", "operation_ref", "report_ref", _RETURN))]},
    "fieldgantt": {"url": False, "restore": [
        _state(("plan_ref", "task_ref", "operation_ref", "report_ref", "scope", "actual_view", _RETURN))]},
    "review": {"url": True, "restore": _REPORT},
    "reports": {"url": True, "restore": _REPORT},
    "calib": {"url": False, "restore": [_state(("scope", "table", "selected", "sample_ref", "table_widths"))]},
    "system": {"url": False, "restore": [_state(("tab", "page_size", "records"))]},
    "trial": {"url": True, "restore": [
        _state(("kind", "draft_ref", "scenario_ref", "base", "scope", "task_origin", _RETURN), requires={"scope": ["base"]},
               excludes={"draft_ref": ["scenario_ref", "base"], "scenario_ref": ["base", "task_origin"]})]},
}

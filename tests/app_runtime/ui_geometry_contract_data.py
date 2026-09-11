"""Current workbench geometry cases and explicit retired-UI boundaries."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, Tuple
from urllib.parse import urlencode

ERROR_PAGE_KEYWORDS: Tuple[str, ...] = (
    "Traceback", "Internal Server Error", "Werkzeug", "500 Internal", "服务器内部错误",
)
DATE = "2026-05-06"
BATCH = "B_UI_GEOMETRY"
PART = "P_UI_GEOMETRY"
PLUGIN_PUBLIC_BEGIN = "几何启动公开诊断"
PLUGIN_PUBLIC_END = "geometry-public-end"
PRIVATE_PATH_CANARY = "APS_GEOMETRY_PRIVATE_PATH_CANARY"
NORMAL_LOG_TEXT = "历史日志里保留 Traceback / Werkzeug / Internal Server Error 字样"
INVALID_PLAN_TEXT = "排产摘要无效，无法确认计划完整性。"

RETIRED_GEOMETRY = {
    "scheduler.config": {
        "path": "/scheduler/config",
        "status": 410,
        "controls": ("freezeWindowEnabled", "preferPrimarySkill", "enforceReadyDefault",
                     "autoAssignEnabled", "orToolsEnabled"),
        "geometry_counted": False,
        "preserved": "ScheduleConfig rows and saved parameter POST, not the old editor",
    },
    "pluginStatusTable": {
        "geometry_counted": False,
        "preserved": "plugins/load startup audit, not a plugin health table",
    },
}

READY_RADIOS = '[role="radiogroup"][aria-label="齐套检查"] input[type="radio"]'
RESOURCE_RADIOS = '[role="radiogroup"][aria-label="缺资源工序"] input[type="radio"]'
PLAN_TABLE = 'table[aria-label="可选排产方案"]'
LOG_TABLE = '.sm-logs-table'
LOG_DETAIL = '.sm-detail[aria-label="日志详情"] pre'


def _case(case, view, selectors, texts, *, action="", **checks):
    return {"case": case, "view": view, "path": "/workbench?" + urlencode({"view": view}),
            "selectors": selectors, "texts": texts, "action": action, **checks}


GEOMETRY_CASES = (
    _case("dashboard", "dashboard", ['[data-dashboard-workspace][data-ready="true"]'],
          ["计划员值班台"], ready='[data-dashboard-workspace][data-ready="true"][aria-busy="false"]'),
    _case("run-preflight", "run", ["[data-preflight-workspace]", 'table[aria-label="排产前检查明细"]'],
          ["排产前检查", BATCH], action="preflight",
          controls={READY_RADIOS: 2, RESOURCE_RADIOS: 2}, tables=['table[aria-label="排产前检查明细"]'],
          notices=[".pf-alert"], summaries=[".pf-metrics"]),
    _case("analysis", "analysis", ["[data-plan-workspace]", '.plan-projections table'],
          ["计划工作区", BATCH], action="plan", plan_scope=True, summaries=[".wb-metrics"]),
    _case("gantt-machine", "gantt", ["[data-plan-gantt]", "[data-plan-inspector]"],
          ["任务详情", BATCH, "几何测试设备"], action="gantt", dimension="machine", plan_scope=True),
    _case("gantt-operator", "gantt", ["[data-plan-gantt]", "[data-plan-inspector]"],
          ["任务详情", BATCH, "几何测试人员"], action="gantt", dimension="operator", plan_scope=True),
    _case("field", "field", ['table[aria-label="现场任务列表"]', ".field-footer"],
          ["现场记录", BATCH], action="field"),
    _case("batch-detail", "batches", ["[data-batch-detail]", 'table[aria-label="批次工序"]'],
          ["批次详情", BATCH], batch_scope=True,
          controls={'[data-batch-detail] input[type="checkbox"]': 1}),
    _case("batch-import", "batches", ['[role="dialog"] input[type="file"]'],
          ["批量维护批次", "新建批次不自动生成工序"], action="batch-import"),
    _case("system-config", "system", ['#sm-panel-config', '#sm-maintenance-auto_backup_enabled'],
          ["本机自动维护配置"], action="system-config",
          controls={'#sm-maintenance-auto_backup_enabled': 1,
                    '#sm-maintenance-auto_backup_cleanup_enabled': 1}),
    _case("system-logs", "system", [LOG_TABLE, LOG_DETAIL],
          ["运行日志与操作记录", "{bad json", "Traceback", "Werkzeug", "Internal Server Error"], action="system-logs",
          log_summary="扩展功能管理 · 切换状态", tables=[LOG_TABLE], multiline=[LOG_DETAIL],
          notices=[".sm-log-sources .sm-note"], summaries=[".sm-metrics"]),
    _case("plugin-startup-audit", "system", [LOG_TABLE, LOG_DETAIL],
          [PLUGIN_PUBLIC_BEGIN, PLUGIN_PUBLIC_END, "插件加载失败，请联系维护人员检查系统运行记录。"],
          action="system-logs", log_summary="扩展功能管理 · 其他操作（load）", tables=[LOG_TABLE], multiline=[LOG_DETAIL],
          notices=[".sm-log-sources .sm-note"], summaries=[".sm-metrics"], plugin_audit=True),
    _case("plan-history", "analysis", [PLAN_TABLE], ["历史版本"], action="history",
          tables=[PLAN_TABLE]),
    _case("plan-invalid-summary", "analysis", [PLAN_TABLE], [INVALID_PLAN_TEXT],
          action="invalid-history", tables=[PLAN_TABLE]),
    _case("process-create", "process", ['[role="dialog"] input[aria-label="图号"]'],
          ["新增零件"], action="process-create"),
    _case("batch-material", "batches", ['table[aria-label="批次物料齐套"]'],
          ["物料齐套原记录", "几何测试物料"], action="batch-material", batch_scope=True),
    _case("reports-overview", "reports", ['.rw-workbench[data-ready="true"]', '.rw-primary-table table'],
          ["报表中心", BATCH], report_scope=True),
    _case("reports-overdue", "reports", ['[aria-label="其他报表目录"] table'],
          ["报表中心", "超期批次"], action="report-catalog", catalog="overdue", report_scope=True),
    _case("reports-utilization", "reports", ['[aria-label="其他报表目录"] table'],
          ["统计窗口：2026-05-06 至 2026-05-06"], action="report-catalog",
          catalog="utilization", resource="operator", report_scope=True),
    _case("reports-execution", "review", ['.er-workbench[data-ready="true"]', '.rw-primary-table table'],
          ["执行复盘", BATCH], report_scope=True),
    _case("reports-downtime", "reports", ['[aria-label="其他报表目录"] table'],
          ["统计窗口：2026-05-06 至 2026-05-06", "几何测试设备"], action="report-catalog",
          catalog="downtime", resource="machine", report_scope=True),
)

EXPECTED_PAGE_SIGNALS: Dict[str, Dict[str, Any]] = {case["case"]: case for case in GEOMETRY_CASES}
UI_GEOMETRY_PAGE_PATHS = tuple(dict.fromkeys(case["path"] for case in GEOMETRY_CASES))
CORE_BROWSER_SMOKE_PATHS = ("/workbench?view=run", "/workbench?view=system")
FULL_UI_CONTRACT_PATHS = UI_GEOMETRY_PAGE_PATHS


def geometry_scenarios(identity: Dict[str, Any]):
    result = []
    for original in GEOMETRY_CASES:
        case = deepcopy(original)
        context: Dict[str, Any] = {}
        if case.get("plan_scope"):
            context = {"plan_ref": identity["plan_ref"],
                       "range_start": DATE + "T00:00:00", "range_end": "2026-05-07T00:00:00"}
        if case.get("batch_scope"):
            context = {"entity_ref": identity["batch_ref"]}
        if case.get("report_scope"):
            scope = {"source": "production", "plan_ref": identity["plan_ref"],
                     "plan_finish_date_from": DATE, "plan_finish_date_to": DATE,
                     "batch_ref": identity["batch_ref"]}
            if case.get("resource"):
                kind = case["resource"]
                scope.update(resource_type=kind, resource_ref=identity[kind + "_ref"])
            context = {"scope": scope}
            if case.get("catalog"):
                context["catalogOpen"] = True
        navigation = {"version": 1, "view": case["view"], "context": context}
        case["path"] = "/workbench?" + urlencode({"view": case["view"], "nav": json.dumps(navigation)})
        case["navigation"] = navigation
        case["identity"] = identity
        result.append(case)
    return result

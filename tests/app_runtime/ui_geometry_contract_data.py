"""为 UI 几何/浏览器冒烟契约测试提供共享基准数据：待校验页面路径清单（UI_GEOMETRY_PAGE_PATHS / CORE_BROWSER_SMOKE_PATHS / FULL_UI_CONTRACT_PATHS）、错误页关键词（ERROR_PAGE_KEYWORDS）以及每个页面应出现的稳定文案/诊断文案/必含元素 id（EXPECTED_PAGE_SIGNALS，部分页另带 forbidden_texts）。"""

from __future__ import annotations

from typing import Dict, Tuple

UI_GEOMETRY_PAGE_PATHS: Tuple[str, ...] = (
    "/?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
    "/scheduler/?status=pending",
    "/scheduler/analysis?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
    "/scheduler/gantt?view=machine&version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&gantt_batch=B_UI_GEOMETRY&gantt_resource=M_UI_GEOMETRY",
    "/scheduler/gantt?view=operator&version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&gantt_batch=B_UI_GEOMETRY&gantt_resource=O_UI_GEOMETRY",
    "/scheduler/resource-dispatch?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&scope_type=machine&machine_id=M_UI_GEOMETRY&batch_id=B_UI_GEOMETRY",
    "/scheduler/config",
    "/scheduler/batches",
    "/scheduler/excel/batches",
    "/system/backup",
    "/system/logs",
    "/system/history",
    "/system/history?version=2",
    "/process/",
    "/material/batches",
    "/reports/?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
    "/reports/overdue?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
    "/reports/utilization?version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&resource_type=operator&resource_id=O_UI_GEOMETRY",
    "/reports/execution-review?version=1&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
    "/reports/downtime?version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&resource_type=machine&resource_id=M_UI_GEOMETRY",
)

CORE_BROWSER_SMOKE_PATHS: Tuple[str, ...] = (
    "/scheduler/?status=pending",
    "/system/logs",
)

FULL_UI_CONTRACT_PATHS: Tuple[str, ...] = UI_GEOMETRY_PAGE_PATHS

ERROR_PAGE_KEYWORDS: Tuple[str, ...] = (
    "Traceback",
    "Internal Server Error",
    "Werkzeug",
    "500 Internal",
    "服务器内部错误",
)

EXPECTED_PAGE_SIGNALS: Dict[str, Dict[str, object]] = {
    "/?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY": {
        "path": "/?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
        "stable_texts": ["计划员值班台", "今日待处理"],
        "diagnostic_texts": [],
        "ids": ["dashboard-workbench-title"],
    },
    "/scheduler/?status=pending": {
        "path": "/scheduler/?status=pending",
        "stable_texts": ["排产调度", "批次列表", "排产操作"],
        "diagnostic_texts": [],
        "ids": ["jsRunScheduleForm", "runEnforceReady", "runStrictMode"],
    },
    "/scheduler/config": {
        "path": "/scheduler/config",
        "stable_texts": ["排产高级设置", "保存当前设置"],
        "diagnostic_texts": [],
        "ids": ["freezeWindowEnabled", "preferPrimarySkill", "enforceReadyDefault", "autoAssignEnabled", "orToolsEnabled"],
    },
    "/scheduler/analysis?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY": {
        "path": "/scheduler/analysis?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
        "stable_texts": ["排产优化分析", "方案对比", "排产分析行动入口"],
        "diagnostic_texts": [],
        "ids": ["schedulerAnalysisWorkbench"],
    },
    "/scheduler/gantt?view=machine&version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&gantt_batch=B_UI_GEOMETRY&gantt_resource=M_UI_GEOMETRY": {
        "path": "/scheduler/gantt?view=machine&version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&gantt_batch=B_UI_GEOMETRY&gantt_resource=M_UI_GEOMETRY",
        "stable_texts": ["甘特图", "任务详情", "点击甘特条查看任务详情"],
        "diagnostic_texts": [],
        "ids": ["ganttTaskDetail"],
    },
    "/scheduler/gantt?view=operator&version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&gantt_batch=B_UI_GEOMETRY&gantt_resource=O_UI_GEOMETRY": {
        "path": "/scheduler/gantt?view=operator&version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&gantt_batch=B_UI_GEOMETRY&gantt_resource=O_UI_GEOMETRY",
        "stable_texts": ["甘特图", "任务详情", "点击甘特条查看任务详情"],
        "diagnostic_texts": [],
        "ids": ["ganttTaskDetail"],
    },
    "/scheduler/resource-dispatch?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&scope_type=machine&machine_id=M_UI_GEOMETRY&batch_id=B_UI_GEOMETRY": {
        "path": "/scheduler/resource-dispatch?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&scope_type=machine&machine_id=M_UI_GEOMETRY&batch_id=B_UI_GEOMETRY",
        "stable_texts": ["资源排班", "任务明细", "现场记录"],
        "diagnostic_texts": [],
        "ids": ["rdTabExecution"],
    },
    "/scheduler/batches": {
        "path": "/scheduler/batches",
        "stable_texts": ["批次管理", "批次列表"],
        "diagnostic_texts": [],
        "ids": ["batchManageStrictMode", "batchesManageTable"],
    },
    "/scheduler/excel/batches": {
        "path": "/scheduler/excel/batches",
        "stable_texts": ["批量维护批次"],
        "diagnostic_texts": [],
        "ids": ["batchImportAutoOps", "batchImportStrictMode"],
    },
    "/system/backup": {
        "path": "/system/backup",
        "stable_texts": ["系统管理 - 备份/恢复", "扩展功能状态"],
        "diagnostic_texts": ["启动问题"],
        "ids": ["backupAutoBackupEnabled", "backupAutoCleanupEnabled", "pluginStatusTable"],
    },
    "/system/logs": {
        "path": "/system/logs",
        "stable_texts": ["系统管理 - 操作日志", "筛选日志"],
        "diagnostic_texts": ["详情格式异常"],
        "ids": ["systemLogsTable"],
    },
    "/system/history": {
        "path": "/system/history",
        "stable_texts": ["系统管理 - 排产历史", "最近排产记录"],
        "diagnostic_texts": [],
        "ids": ["systemHistoryTable"],
    },
    "/system/history?version=2": {
        "path": "/system/history?version=2",
        "stable_texts": ["系统管理 - 排产历史", "版本详情：v2"],
        "diagnostic_texts": ["当前版本的排产摘要读取失败"],
        "ids": ["systemHistoryTable"],
    },
    "/process/": {
        "path": "/process/",
        "stable_texts": ["零件工艺模板"],
        "diagnostic_texts": [],
        "ids": ["processCreateStrictMode", "partsTable"],
    },
    "/material/batches": {
        "path": "/material/batches",
        "stable_texts": ["批次物料需求"],
        "diagnostic_texts": [],
        "ids": ["batchMaterialBatchSelect"],
    },
    "/reports/?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY": {
        "path": "/reports/?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
        "stable_texts": ["报表中心", "超期清单", "资源负荷与利用率", "计划和现场实际", "停机影响统计"],
        "forbidden_texts": [
            "当前正式采用方案",
            "请切换到正式采用方案",
            "这张表只看正式采用方案",
            "这张表只复盘正式采用方案",
        ],
        "diagnostic_texts": [],
        "ids": ["reportsOverview", "reportsEntryCards"],
    },
    "/reports/overdue?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY": {
        "path": "/reports/overdue?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
        "stable_texts": ["报表 - 超期清单", "结果明细", "不能证明", "继续处理"],
        "diagnostic_texts": [],
        "ids": ["overdueTable"],
    },
    "/reports/utilization?version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&resource_type=operator&resource_id=O_UI_GEOMETRY": {
        "path": "/reports/utilization?version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&resource_type=operator&resource_id=O_UI_GEOMETRY",
        "stable_texts": ["报表 - 资源负荷与利用率", "设备负荷", "人员负荷", "继续处理"],
        "diagnostic_texts": [],
        "ids": ["utilizationMachineTable", "utilizationOperatorTable"],
    },
    "/reports/execution-review?version=1&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY": {
        "path": "/reports/execution-review?version=1&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
        "stable_texts": ["报表 - 计划和现场实际", "历史正式方案", "计划和现场实际", "继续处理"],
        "forbidden_texts": [
            "当前正式采用方案",
            "请切换到正式采用方案",
            "这张表只看正式采用方案",
            "这张表只复盘正式采用方案",
        ],
        "diagnostic_texts": [],
        "ids": ["executionReviewTable"],
    },
    "/reports/downtime?version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&resource_type=machine&resource_id=M_UI_GEOMETRY": {
        "path": "/reports/downtime?version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&resource_type=machine&resource_id=M_UI_GEOMETRY",
        "stable_texts": ["报表 - 停机影响统计", "设备级停机", "几何测试设备", "继续处理"],
        "diagnostic_texts": [],
        "ids": ["downtimeTable"],
    },
}

for _signals in EXPECTED_PAGE_SIGNALS.values():
    _signals["texts"] = list(_signals.get("stable_texts") or ())

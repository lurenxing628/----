from __future__ import annotations

from typing import Dict, Tuple

UI_GEOMETRY_PAGE_PATHS: Tuple[str, ...] = (
    "/scheduler/?status=pending",
    "/scheduler/config",
    "/scheduler/batches",
    "/scheduler/excel/batches",
    "/system/backup",
    "/system/logs",
    "/system/history",
    "/system/history?version=2",
    "/process/",
    "/material/batches",
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
}

for _signals in EXPECTED_PAGE_SIGNALS.values():
    _signals["texts"] = list(_signals.get("stable_texts") or ())

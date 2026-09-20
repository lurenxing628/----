"""系统维护记录只读事实：清理动作的操作日志窗口。"""

from __future__ import annotations

from typing import Any, Dict, List

from .base_repo import BaseRepository


class WorkbenchSystemMaintenanceRepository(BaseRepository):
    def cleanup_audit_rows(self, limit: int) -> List[Dict[str, Any]]:
        """system 模块 cleanup / logs_cleanup 动作的日志，按 id 倒序取 limit 条。"""
        return self.fetchall(
            "SELECT id,log_time,log_level,module,action,detail,error_message FROM OperationLogs "
            "WHERE module='system' AND action IN ('cleanup','logs_cleanup') ORDER BY id DESC LIMIT ?",
            (limit,))

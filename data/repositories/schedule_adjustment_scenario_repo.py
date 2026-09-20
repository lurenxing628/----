from __future__ import annotations

from typing import Any, Dict, List

from .base_repo import BaseRepository


class ScheduleAdjustmentScenarioRepository(BaseRepository):
    """已保存模拟方案的只读目录读取。

    写入方（甘特调整 Draft / Scenario / Validation 服务）已于 2026-09-20 随旧路由层退役；
    工作台计划目录仍按目录顺序读取历史方案头。
    """

    def list_catalog_rows(self) -> List[Dict[str, Any]]:
        """全部模拟方案原始行，按目录顺序：base_version 降序、created_at 降序、scenario_id。"""
        return self.fetchall(
            "SELECT * FROM ScheduleAdjustmentScenario ORDER BY base_version DESC, created_at DESC, scenario_id"
        )

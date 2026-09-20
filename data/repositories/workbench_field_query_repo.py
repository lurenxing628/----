"""现场（报工文件 / 现场工作台）只读事实：可用设备人员索引、最新排产版本、批次零件名。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_repo import BaseRepository


class WorkbenchFieldQueryRepository(BaseRepository):
    def active_resource_index_rows(self) -> List[Dict[str, Any]]:
        """有效的设备/人员系统编号及其名称（ref, kind, entity_key, label）。"""
        return self.fetchall("""SELECT e.ref,e.kind,e.entity_key,
            CASE WHEN e.kind='machine' THEN m.name ELSE o.name END AS label
            FROM WorkbenchEntityRefs e
            LEFT JOIN Machines m ON e.kind='machine' AND m.machine_id=e.entity_key
            LEFT JOIN Operators o ON e.kind='operator' AND o.operator_id=e.entity_key
            WHERE e.active=1 AND e.kind IN ('machine','operator')""")

    def latest_schedule_version(self) -> Optional[int]:
        """ScheduleHistory 里最大的版本号；没有历史时为 None。"""
        return self.fetchvalue("SELECT MAX(version) FROM ScheduleHistory")

    def batch_part_names(self) -> Dict[str, Any]:
        """{batch_id: part_name}；零件缺失时值为 None。"""
        rows = self.fetchall("SELECT b.batch_id,p.part_name FROM Batches b LEFT JOIN Parts p ON p.part_no=b.part_no")
        return {row["batch_id"]: row["part_name"] for row in rows}

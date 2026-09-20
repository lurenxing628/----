"""工时文件写入口：带系统编号修订守卫的工序工时 / 外协组周期更新。

列名由本模块白名单展开；只返回影响行数，stale 判定归调用方服务。
"""

from __future__ import annotations

from typing import Any, Dict, Sequence

from .base_repo import BaseRepository

OPERATION_HOUR_COLUMNS = ("setup_hours", "unit_hours", "ext_days")
GROUP_CYCLE_COLUMNS = ("total_days",)


def _assignments(values: Dict[str, Any], allowed: Sequence[str]) -> str:
    if not values:
        raise ValueError("no columns to update")
    for column in values:
        if column not in allowed:
            raise ValueError("column not allowed: " + repr(column))
    return ",".join(column + "=?" for column in values)


class WorkbenchProcessHoursRepository(BaseRepository):
    def update_operation_hours(self, op_id: int, values: Dict[str, Any], *, ref: str, revision: int) -> int:
        """按 id 改工序工时列；仅当该工序的有效系统编号修订仍是 revision 时生效。"""
        assignments = _assignments(values, OPERATION_HOUR_COLUMNS)
        cursor = self.execute(
            "UPDATE PartOperations SET " + assignments + " WHERE id=? AND EXISTS "
            "(SELECT 1 FROM WorkbenchEntityRefs WHERE ref=? AND revision=? AND active=1 "
            "AND entity_key=CAST(PartOperations.id AS TEXT))",
            list(values.values()) + [op_id, ref, revision])
        return int(cursor.rowcount)

    def update_group_cycle(self, group_id: str, values: Dict[str, Any], *, ref: str, revision: int) -> int:
        """按 group_id 改外协组周期列；仅当该组的有效系统编号修订仍是 revision 时生效。"""
        assignments = _assignments(values, GROUP_CYCLE_COLUMNS)
        cursor = self.execute(
            "UPDATE ExternalGroups SET " + assignments + " WHERE group_id=? AND EXISTS "
            "(SELECT 1 FROM WorkbenchEntityRefs WHERE ref=? AND revision=? AND active=1 "
            "AND entity_key=CAST(ExternalGroups.group_id AS TEXT))",
            list(values.values()) + [group_id, ref, revision])
        return int(cursor.rowcount)

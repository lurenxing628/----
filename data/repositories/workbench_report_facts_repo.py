"""现场分析（报表）只读事实：正式计划工序数、设备/人员名称映射。"""

from __future__ import annotations

from typing import Any, Dict, Iterable

from .base_repo import BaseRepository

_NAME_SQL_PREFIX = {
    "machine": "SELECT machine_id, name FROM Machines WHERE machine_id IN (",
    "operator": "SELECT operator_id, name FROM Operators WHERE operator_id IN (",
}
RESOURCE_NAME_KINDS = tuple(_NAME_SQL_PREFIX)
_NAME_CHUNK = 400


class WorkbenchReportFactsRepository(BaseRepository):
    def schedule_operation_count(self, version: int) -> int:
        return self.fetchvalue("SELECT COUNT(*) FROM Schedule WHERE version=?", (version,))

    def resource_names(self, kind: str, keys: Iterable[str]) -> Dict[str, Any]:
        """{str(业务键): name}，按 400 个一批查询；kind 只能是 machine / operator。"""
        if kind not in _NAME_SQL_PREFIX:
            raise ValueError("unsupported resource kind: " + repr(kind))
        prefix = _NAME_SQL_PREFIX[kind]
        values = list(keys)
        labels: Dict[str, Any] = {}
        for start in range(0, len(values), _NAME_CHUNK):
            chunk = values[start:start + _NAME_CHUNK]
            sql = prefix + ",".join("?" for _ in chunk) + ")"
            labels.update((str(row[0]), row[1]) for row in self.execute(sql, chunk))
        return labels

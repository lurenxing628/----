"""候选排产输入读模型：原安排锁定行、工作日历/停机原始行、采用校验用主数据表、零工时冻结点。

只返回原始行字典；班次/停机合法性、锁定区间与零工时依据的裁决归 core/services/workbench/run_input_runtime、
run_input_points 与 run_candidate_adoption_constraints。表名一律来自本模块常量，不接受调用方传表名。
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Sequence, Tuple

from .base_repo import BaseRepository
from .schedule_time_sql import register_schedule_time_sql_functions, time_dt

CALENDAR_TABLES = ("WorkCalendar", "OperatorCalendar")
ADOPTION_CHECK_TABLES = ("Machines", "MachineOpTypes", "Operators", "Suppliers", "OpTypes", "OperatorMachine", "OperatorSkill",
                         "WorkbenchOperatorProfiles", "WorkbenchSupplierOpTypes", "PartOperations", "ExternalGroups",
                         "BatchMaterials", "BatchMaterialReviews", "BatchMaterialStages", "BatchMaterialArrivals", "BatchQuantitySplits", "BatchExternalContexts", "BatchOperations")
_POINT_CHUNK = 900


class WorkbenchRunInputRepository(BaseRepository):
    def __init__(self, conn, logger=None):
        super().__init__(conn, logger=logger)
        register_schedule_time_sql_functions(conn)

    def schedule_rows_through_version(self, prev_version: int) -> Iterator[Dict[str, Any]]:
        """流式产出 version<=prev_version 的全部 Schedule 行，按 version,id 排序（同一工序后版本覆盖前版本）。

        历史版本可能有几十万行，调用方只保留最新一行，所以这里不整体物化。"""
        return self.iter_rows("SELECT * FROM Schedule WHERE version<=? ORDER BY version,id", (prev_version,))

    def calendar_rows(self) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """流式产出 (表名, 行)，按 CALENDAR_TABLES 顺序逐表读取；两条语句都在调用时执行，错误立即翻译。"""
        streams = [(table, self.iter_rows("SELECT * FROM " + table)) for table in CALENDAR_TABLES]
        return ((table, row) for table, stream in streams for row in stream)

    def machine_downtime_rows(self) -> Iterator[Dict[str, Any]]:
        return self.iter_rows("SELECT * FROM MachineDowntimes")

    def adoption_check_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        """{表名: 全部行}，按 ADOPTION_CHECK_TABLES 顺序，供 PreflightChecks 复核候选实际资源。"""
        return {name: self.fetchall('SELECT * FROM "' + name + '"') for name in ADOPTION_CHECK_TABLES}

    def point_rows_at(self, *, version: int, op_ids: Sequence[int], start_time: Any) -> List[Dict[str, Any]]:
        """指定版本里 op_ids 中开工=完工=start_time 的零工时行；op_ids 按 900 一片分批，不去重。"""
        rows: List[Dict[str, Any]] = []
        for offset in range(0, len(op_ids), _POINT_CHUNK):
            keys = list(op_ids[offset:offset + _POINT_CHUNK])
            marks = ",".join("?" for _ in keys)
            sql = ("SELECT op_id,machine_id,operator_id,start_time,end_time FROM Schedule "
                   "WHERE version=? AND op_id IN (" + marks + ") AND "
                   + time_dt(None, "start_time") + "=aps_parse_dt(?) AND "
                   + time_dt(None, "end_time") + "=aps_parse_dt(?)")
            rows.extend(self.fetchall(sql, [version] + keys + [start_time, start_time]))
        return rows

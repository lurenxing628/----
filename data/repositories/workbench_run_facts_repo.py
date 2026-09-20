"""排产接收事实读模型：整库事实快照、永久身份、正式基线与正式安排一致性探针。

只返回原始行、标量与布尔；hash/durable 编码、基线歧义判定和 snapshot_stale 裁决归 core/services/workbench/run_jobs_facts
与 run_candidate_adoption_storage。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.schema_probe import SchemaObject, schema_objects
from core.infrastructure.workbench_run_schema import RUN_TABLES

from .base_repo import BaseRepository


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class WorkbenchRunFactsRepository(BaseRepository):
    def admission_facts(self) -> Tuple[List[SchemaObject], Dict[str, List[Tuple[Any, ...]]]]:
        """(sqlite_master 有序对象清单, {表名: [按 rowid 排序的原始行元组]})。

        排产账本四张表不入快照；WorkbenchCommandReceipts 只取非 scheduling.run 的回执。
        表名来自 sqlite_master 自省而非调用方参数，这里不是按名读表的逃生口。
        """
        schema = schema_objects(self.conn)
        tables: Dict[str, List[Tuple[Any, ...]]] = {}
        for kind, name, _, _ in schema:
            if kind != "table" or name in RUN_TABLES:
                continue
            sql = "SELECT * FROM " + _quote(name)
            if name == "WorkbenchCommandReceipts":
                sql += " WHERE action <> 'scheduling.run'"
            tables[name] = [tuple(row) for row in self.execute(sql + " ORDER BY rowid")]
        return schema, tables

    def operation_identity_refs(self) -> List[Tuple[Any, ...]]:
        """[(source_key, ref)]：所有生效的工序永久身份。"""
        return [tuple(row) for row in self.execute(
            "SELECT source_key,ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1")]

    def batch_operation_batch_refs(self) -> List[Tuple[Any, ...]]:
        """[(BatchOperations.id, 所属批次的永久 ref)]。"""
        return [tuple(row) for row in self.execute("""SELECT bo.id,r.ref FROM BatchOperations bo
        JOIN WorkbenchEntityRefs r ON r.kind='batch' AND r.entity_key=bo.batch_id AND r.active=1""")]

    def piece_batch_refs(self) -> List[str]:
        """带 piece_id 的批次工序所属批次 ref（可重复）。"""
        return [row[0] for row in self.execute("SELECT r.ref FROM BatchOperations bo JOIN WorkbenchEntityRefs r "
            "ON r.kind='batch' AND r.entity_key=bo.batch_id AND r.active=1 WHERE bo.piece_id IS NOT NULL").fetchall()]

    def latest_history_version(self) -> Optional[int]:
        return self.execute("SELECT MAX(version) FROM ScheduleHistory").fetchone()[0]

    def official_plan_refs(self, version: int) -> List[str]:
        return [row[0] for row in self.execute(
            "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='official' AND active=1 AND version=?", (version,)).fetchall()]

    def schedule_rows_for_version(self, version: int) -> List[Dict[str, Any]]:
        return self.fetchall("SELECT * FROM Schedule WHERE version=? ORDER BY id", (version,))

    def history_result_summaries(self, version: int) -> List[Any]:
        """该版本在 ScheduleHistory 里的 result_summary 列表（正常应恰好一条）。"""
        return [row[0] for row in self.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?", (version,))]

    def schedule_has_rows(self) -> bool:
        return self.execute("SELECT 1 FROM Schedule LIMIT 1").fetchone() is not None

    def schedule_has_rows_without_history(self) -> bool:
        return self.execute("SELECT 1 FROM Schedule s WHERE NOT EXISTS "
                            "(SELECT 1 FROM ScheduleHistory h WHERE h.version=s.version) LIMIT 1").fetchone() is not None

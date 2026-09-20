"""排产记录目录读模型（WorkbenchRunJobs / Receipts / Candidates / Tasks / CommandReceipts）的只读查询。

只返回容量事实、孤儿探针结果和目录行；上限判定与一致性裁决归 core/services/workbench/run_history_storage。
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base_repo import BaseRepository

# 目录容量按这三张“文档表”统计；WorkbenchCommandReceipts 只算 scheduling.run 的接收回执。
DIRECTORY_DOCUMENT_TABLES = (
    ("WorkbenchRunJobs", ("normalized_input_json",)),
    ("WorkbenchRunReceipts", ("result_json",)),
    ("WorkbenchCommandReceipts", ("outcome_json",)),
)

_ORPHAN_PROBES = (
    ("receipts_without_job",
     "SELECT 1 FROM WorkbenchRunReceipts r LEFT JOIN WorkbenchRunJobs j ON j.run_ref=r.run_ref WHERE j.run_ref IS NULL LIMIT 1"),
    ("candidates_without_job",
     "SELECT 1 FROM WorkbenchRunCandidates c LEFT JOIN WorkbenchRunJobs j ON j.run_ref=c.run_ref WHERE j.run_ref IS NULL LIMIT 1"),
    ("tasks_without_candidate",
     "SELECT 1 FROM WorkbenchRunCandidateTasks t LEFT JOIN WorkbenchRunCandidates c ON c.candidate_ref=t.candidate_ref WHERE c.candidate_ref IS NULL LIMIT 1"),
    ("admissions_without_job",
     "SELECT 1 FROM WorkbenchCommandReceipts a LEFT JOIN WorkbenchRunJobs j ON j.request_key=a.request_key WHERE a.action='scheduling.run' AND j.run_ref IS NULL LIMIT 1"),
)


class WorkbenchRunHistoryQueryRepository(BaseRepository):
    def directory_capacity(self) -> Dict[str, Dict[str, int]]:
        """{table: {"rows": 行数, "bytes": 文档总字节, "max_document_bytes": 最大单文档字节}}，按 DIRECTORY_DOCUMENT_TABLES 顺序。"""
        result: Dict[str, Dict[str, int]] = {}
        for table, fields in DIRECTORY_DOCUMENT_TABLES:
            size = "+".join("length(CAST(" + field + " AS BLOB))" for field in fields)
            where = " WHERE action='scheduling.run'" if table == "WorkbenchCommandReceipts" else ""
            row = self.execute("SELECT COUNT(*),COALESCE(SUM(" + size + "),0),COALESCE(MAX(" + size + "),0) FROM " + table + where).fetchone()
            result[table] = {"rows": row[0], "bytes": row[1], "max_document_bytes": row[2]}
        return result

    def candidate_count(self) -> int:
        return self.execute("SELECT COUNT(*) FROM WorkbenchRunCandidates").fetchone()[0]

    def orphan_probe(self) -> Dict[str, bool]:
        """反连接探针：即使旧写入方关掉了 foreign_keys，也能发现无父行的回执/候选/明细/接收回执。"""
        return {name: self.execute(sql).fetchone() is not None for name, sql in _ORPHAN_PROBES}

    def list_jobs(self) -> List[Dict[str, Any]]:
        return self.fetchall("""SELECT j.run_ref,j.state,j.stage,j.accepted_at,
            j.started_at,j.finished_at,j.normalized_input_json,j.input_ref,j.executor_ref,
            a.action AS admission_action,a.context_ref AS admission_context,a.outcome_json AS admission_json,
            r.state AS receipt_state,r.result_json,r.recorded_at
            FROM WorkbenchRunJobs j LEFT JOIN WorkbenchCommandReceipts a ON a.request_key=j.request_key
            LEFT JOIN WorkbenchRunReceipts r ON r.run_ref=j.run_ref ORDER BY j.run_ref""")

    def list_candidates(self) -> List[Dict[str, Any]]:
        return self.fetchall("""SELECT c.run_ref,c.candidate_ref,c.status,c.sequence,
            c.task_count,COUNT(t.row_ref) AS actual_count,MIN(t.ordinal) AS first_ordinal,MAX(t.ordinal) AS last_ordinal
            FROM WorkbenchRunCandidates c LEFT JOIN WorkbenchRunCandidateTasks t ON t.candidate_ref=c.candidate_ref
            GROUP BY c.candidate_ref ORDER BY c.run_ref,c.sequence,c.candidate_ref""")

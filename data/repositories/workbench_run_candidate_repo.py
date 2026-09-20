"""永久候选读模型：按 run_ref / candidate_ref 读排产作业、回执、候选与工序明细的有界事实。

只返回长度、计数与原始行（元组/字典）；容量上限、损坏判定与 404 裁决归 core/services/workbench/run_candidate_storage。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .base_repo import BaseRepository


class WorkbenchRunCandidateRepository(BaseRepository):
    def job_summary(self, run_ref: str) -> Optional[Tuple[Any, ...]]:
        """(run_ref,state,accepted_at,finished_at, 输入/执行/基线/事实四份 JSON 的字节数)；没有该作业返回 None。"""
        row = self.execute("""SELECT run_ref,state,accepted_at,finished_at,
            length(CAST(normalized_input_json AS BLOB)),length(CAST(execution_json AS BLOB)),
            length(CAST(baseline_json AS BLOB)),length(CAST(facts_json AS BLOB))
            FROM WorkbenchRunJobs WHERE run_ref=?""", (run_ref,)).fetchone()
        return tuple(row) if row is not None else None

    def receipt_size(self, run_ref: str) -> Optional[int]:
        row = self.execute("SELECT length(CAST(result_json AS BLOB)) FROM WorkbenchRunReceipts WHERE run_ref=?",
                           (run_ref,)).fetchone()
        return row[0] if row is not None else None

    def receipt_state_and_result(self, run_ref: str) -> Optional[Tuple[Any, ...]]:
        row = self.execute("SELECT state,result_json FROM WorkbenchRunReceipts WHERE run_ref=?",
                           (run_ref,)).fetchone()
        return tuple(row) if row is not None else None

    def candidate_sizes(self, run_ref: str, limit: int) -> List[Tuple[Any, ...]]:
        """[(candidate_ref, artifact 字节数, task_count)]，按 sequence 排序，最多 limit 行。"""
        return [tuple(row) for row in self.execute("""SELECT candidate_ref,length(CAST(artifact_json AS BLOB)),task_count
            FROM WorkbenchRunCandidates WHERE run_ref=? ORDER BY sequence LIMIT ?""", (run_ref, limit))]

    def candidate_task_counts(self, run_ref: str) -> Dict[str, int]:
        return {row[0]: row[1] for row in self.execute("""SELECT t.candidate_ref,COUNT(*)
            FROM WorkbenchRunCandidates c JOIN WorkbenchRunCandidateTasks t ON t.candidate_ref=c.candidate_ref
            WHERE c.run_ref=? GROUP BY t.candidate_ref""", (run_ref,))}

    def candidate_rows(self, run_ref: str) -> List[Tuple[Any, ...]]:
        """[(candidate_ref,run_ref,status,task_count,sequence,artifact_json)]，按 sequence 排序。"""
        return [tuple(row) for row in self.execute("""SELECT candidate_ref,run_ref,status,task_count,sequence,artifact_json
            FROM WorkbenchRunCandidates WHERE run_ref=? ORDER BY sequence""", (run_ref,))]

    def candidate_run_ref(self, candidate_ref: str) -> Optional[str]:
        row = self.execute("SELECT run_ref FROM WorkbenchRunCandidates WHERE candidate_ref=?", (candidate_ref,)).fetchone()
        return row[0] if row is not None else None

    def job_capture(self, run_ref: str) -> Optional[Tuple[Any, ...]]:
        """(normalized_input_json,execution_json,baseline_json,facts_json,facts_hash)；没有该作业返回 None。"""
        row = self.execute("""SELECT normalized_input_json,execution_json,baseline_json,facts_json,facts_hash
            FROM WorkbenchRunJobs WHERE run_ref=?""", (run_ref,)).fetchone()
        return tuple(row) if row is not None else None

    def task_sizes(self, candidate_ref: str) -> Tuple[Any, ...]:
        """(明细行数, payload 总字节, 最大单行 payload 字节)。"""
        return tuple(self.execute("""SELECT COUNT(*),COALESCE(SUM(length(CAST(payload_json AS BLOB))),0),
            COALESCE(MAX(length(CAST(payload_json AS BLOB))),0)
            FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?""", (candidate_ref,)).fetchone())

    def task_rows(self, candidate_ref: str) -> List[Tuple[Any, ...]]:
        """[(row_ref,operation_ref,ordinal,payload_json)]，按 ordinal 排序。"""
        return [tuple(row) for row in self.execute("""SELECT row_ref,operation_ref,ordinal,payload_json
            FROM WorkbenchRunCandidateTasks WHERE candidate_ref=? ORDER BY ordinal""", (candidate_ref,))]

    def adoption_receipt_capacity(self, action: str, candidate_ref: str) -> Tuple[Any, ...]:
        """(该候选下 action 回执条数, outcome_json 总字节)。"""
        return tuple(self.execute("SELECT COUNT(*),COALESCE(SUM(length(CAST(outcome_json AS BLOB))),0) "
                                  "FROM WorkbenchCommandReceipts WHERE action=? AND context_ref=?", (action, candidate_ref)).fetchone())

    def adoption_receipts(self, action: str, candidate_ref: str) -> List[Dict[str, Any]]:
        return self.fetchall("SELECT * FROM WorkbenchCommandReceipts WHERE action=? AND context_ref=? "
                             "ORDER BY committed_at_utc,request_key", (action, candidate_ref))

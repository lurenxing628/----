"""永久候选读模型：按 run_ref / candidate_ref 读排产作业、回执、候选与工序明细的有界事实。

只返回原始行及实际读取的字节数；容量上限、损坏判定与 404 裁决归 facts/candidate_store。
"""

from __future__ import annotations

from typing import Any, Iterator, Optional, Tuple

from .base_repo import BaseRepository


class WorkbenchRunCandidateRepository(BaseRepository):
    def job_head(self, run_ref: str) -> Optional[Tuple[Any, ...]]:
        """(run_ref,state,accepted_at,finished_at)，不读取生产归档。"""
        row = self.execute("""SELECT run_ref,state,accepted_at,finished_at
            FROM WorkbenchRunJobs WHERE run_ref=?""", (run_ref,)).fetchone()
        return tuple(row) if row is not None else None

    def receipt_state_and_result(self, run_ref: str) -> Optional[Tuple[Any, ...]]:
        row = self.execute("SELECT state,result_json,length(CAST(result_json AS BLOB)) "
                           "FROM WorkbenchRunReceipts WHERE run_ref=?",
                           (run_ref,)).fetchone()
        return tuple(row) if row is not None else None

    def candidate_rows(self, run_ref: str, limit: int) -> Iterator[Tuple[Any, ...]]:
        """候选原件和 artifact 字节数，按 sequence 有界逐行读取。"""
        rows = self.execute("""SELECT candidate_ref,run_ref,status,task_count,sequence,artifact_json,
            length(CAST(artifact_json AS BLOB)) FROM WorkbenchRunCandidates
            WHERE run_ref=? ORDER BY sequence LIMIT ?""", (run_ref, limit))
        return (tuple(row) for row in rows)

    def candidate_row(self, candidate_ref: str) -> Optional[Tuple[Any, ...]]:
        """只取这份永久候选的原件与字节数。"""
        row = self.execute("""SELECT candidate_ref,run_ref,status,task_count,sequence,artifact_json,
            length(CAST(artifact_json AS BLOB)) FROM WorkbenchRunCandidates
            WHERE candidate_ref=?""", (candidate_ref,)).fetchone()
        return tuple(row) if row is not None else None

    def candidate_run_ref(self, candidate_ref: str) -> Optional[str]:
        row = self.execute("SELECT run_ref FROM WorkbenchRunCandidates WHERE candidate_ref=?", (candidate_ref,)).fetchone()
        return row[0] if row is not None else None

    def candidate_identity(self, candidate_ref: str):
        """永久 PK 与已保存 summary 小头；缺读模型由读取边界裁决。"""
        return self.fetchone("""SELECT c.candidate_ref,c.run_ref,c.status,
            m.projection_version,m.summary_json,length(CAST(m.summary_json AS BLOB)) AS summary_bytes
            FROM WorkbenchRunCandidates c LEFT JOIN WorkbenchRunCandidateReadModels m
            ON m.candidate_ref=c.candidate_ref AND m.run_ref=c.run_ref WHERE c.candidate_ref=?""", (candidate_ref,))

    def job_capture(self, run_ref: str) -> Optional[Tuple[Any, ...]]:
        """四份生产原件、兼容 facts_hash 和各原件实际字节数。"""
        row = self.execute("""SELECT normalized_input_json,execution_json,baseline_json,facts_json,facts_hash,
            length(CAST(normalized_input_json AS BLOB)),length(CAST(execution_json AS BLOB)),
            length(CAST(baseline_json AS BLOB)),length(CAST(facts_json AS BLOB))
            FROM WorkbenchRunJobs WHERE run_ref=?""", (run_ref,)).fetchone()
        return tuple(row) if row is not None else None

    def task_rows(self, candidate_ref: str, limit: int) -> Iterator[Tuple[Any, ...]]:
        """任务原件和 payload 字节数，按 ordinal 有界逐行读取。"""
        rows = self.execute("""SELECT row_ref,operation_ref,ordinal,payload_json,
            length(CAST(payload_json AS BLOB)) FROM WorkbenchRunCandidateTasks
            WHERE candidate_ref=? ORDER BY ordinal LIMIT ?""", (candidate_ref, limit))
        return (tuple(row) for row in rows)

    def adoption_receipts(self, action: str, candidate_ref: str, limit: int):
        return self.iter_rows("SELECT * FROM WorkbenchCommandReceipts WHERE action=? AND context_ref=? "
                              "ORDER BY committed_at_utc,request_key LIMIT ?", (action, candidate_ref, limit))

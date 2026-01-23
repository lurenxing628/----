from __future__ import annotations

from typing import List, Optional

from core.models import SystemJobState

from .base_repo import BaseRepository


class SystemJobStateRepository(BaseRepository):
    """系统任务状态仓库（SystemJobState）。用于记录自动任务上次执行时间。"""

    def get(self, job_key: str) -> Optional[SystemJobState]:
        row = self.fetchone(
            "SELECT id, job_key, last_run_time, last_run_detail, updated_at FROM SystemJobState WHERE job_key = ?",
            (str(job_key),),
        )
        return SystemJobState.from_row(row) if row else None

    def list_all(self) -> List[SystemJobState]:
        rows = self.fetchall("SELECT id, job_key, last_run_time, last_run_detail, updated_at FROM SystemJobState ORDER BY job_key")
        return [SystemJobState.from_row(r) for r in rows]

    def set_last_run(self, job_key: str, last_run_time: Optional[str], last_run_detail: Optional[str] = None) -> None:
        self.execute(
            """
            INSERT INTO SystemJobState (job_key, last_run_time, last_run_detail, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(job_key) DO UPDATE SET
              last_run_time = excluded.last_run_time,
              last_run_detail = excluded.last_run_detail,
              updated_at = CURRENT_TIMESTAMP
            """,
            (str(job_key), last_run_time, last_run_detail),
        )


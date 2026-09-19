"""工艺工作流确认表（WorkbenchProcessWorkflow / WorkbenchProcessOperationConfirmations）的写入口。

只做 SQL 执行与参数绑定；阶段列名由本仓储内的白名单展开，裁决与事务归调用方服务。
"""

from __future__ import annotations

from typing import Optional

from .base_repo import BaseRepository

WORKFLOW_STAGES = ("route", "source", "hours")


class WorkbenchProcessWorkflowRepository(BaseRepository):
    def insert_workflow(self, part_ref: str) -> None:
        self.execute("INSERT INTO WorkbenchProcessWorkflow(part_ref) VALUES (?)", (part_ref,))

    def insert_confirmation(
        self,
        *,
        part_ref: str,
        operation_ref: str,
        stage: str,
        signature: str,
        confirmed_at: str,
        confirmed_by: Optional[str],
    ) -> None:
        self.execute(
            """INSERT INTO WorkbenchProcessOperationConfirmations
                (part_ref,operation_ref,stage,signature,confirmed_at,confirmed_by) VALUES (?,?,?,?,?,?)""",
            (part_ref, operation_ref, stage, signature, confirmed_at, confirmed_by),
        )

    def update_confirmation(
        self,
        *,
        part_ref: str,
        operation_ref: str,
        stage: str,
        signature: str,
        confirmed_at: str,
        confirmed_by: Optional[str],
    ) -> int:
        cursor = self.execute(
            """UPDATE WorkbenchProcessOperationConfirmations SET signature=?,confirmed_at=?,confirmed_by=?
                WHERE part_ref=? AND operation_ref=? AND stage=?""",
            (signature, confirmed_at, confirmed_by, part_ref, operation_ref, stage),
        )
        return int(cursor.rowcount)

    def delete_confirmations_outside_active_route(self, part_ref: str, part_no: str) -> int:
        cursor = self.execute(
            """DELETE FROM WorkbenchProcessOperationConfirmations WHERE part_ref=? AND operation_ref NOT IN (
                SELECT r.ref FROM PartOperations o JOIN WorkbenchEntityRefs r ON r.entity_key=CAST(o.id AS TEXT)
                WHERE r.kind='template_operation' AND r.active=1 AND o.part_no=? AND o.status='active')""",
            (part_ref, part_no),
        )
        return int(cursor.rowcount)

    def set_stage_confirmation(
        self,
        *,
        part_ref: str,
        stage: str,
        signature: str,
        confirmed_at: str,
        confirmed_by: Optional[str],
    ) -> int:
        if stage not in WORKFLOW_STAGES:
            raise ValueError(f"unknown workflow stage: {stage!r}")
        cursor = self.execute(
            f"""UPDATE WorkbenchProcessWorkflow SET {stage}_signature=?,
                {stage}_confirmed_at=?,{stage}_confirmed_by=? WHERE part_ref=?""",
            (signature, confirmed_at, confirmed_by, part_ref),
        )
        return int(cursor.rowcount)

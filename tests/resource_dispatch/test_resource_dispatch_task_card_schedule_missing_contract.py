"""回归测试（N4/O31）：ResourceDispatchExecutionService.task_card_for_feedback_context 在
对应排程行缺失时，必须抛 AppError(ErrorCode.NOT_FOUND)（"资源不存在"语义），而非旧的
ValidationError(field=schedule_id)——与写门禁 operation_execution_feedback_service 的 schedule
缺失分支同错误类，跨文件对称；错误经路由冒泡到全局 errorhandler(AppError) 渲染为 404，而非
被当字段校验错（400/422）。另两处 ValidationError（缺查询对象 / 不在当前计划身份里）是合法的
输入/状态校验，刻意不改。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.errors import AppError, ErrorCode
from core.services.scheduler.operation_execution_feedback_support import ExecutionFeedbackContext
from core.services.scheduler.resource_dispatch_execution_service import ResourceDispatchExecutionService
from tests._support.paths import REPO_ROOT


def _connect_fresh_schema(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _context(schedule_id: int) -> ExecutionFeedbackContext:
    return ExecutionFeedbackContext(
        schedule_version=1,
        schedule_id=schedule_id,
        op_id=1,
        batch_id="B1",
        expected_state_revision="",
        created_by="t",
        idempotency_key="k",
        requested_plan_role="adopted",
        source_table="Schedule",
        effective_plan_role="adopted",
        scenario_id=None,
    )


def test_task_card_missing_schedule_raises_not_found(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        svc = ResourceDispatchExecutionService(conn)
        # 空库：schedule_repo.get(任意 id) 必为 None → 走缺失分支；state 在 raise 之前从不被读取。
        with pytest.raises(AppError) as exc_info:
            svc.task_card_for_feedback_context(_context(999999), None, feedback_write_enabled=True)
        assert exc_info.value.code == ErrorCode.NOT_FOUND, (
            f"排程行缺失须 NOT_FOUND（资源不存在语义），不得当字段校验错，实际 {exc_info.value.code!r}"
        )
        assert "排程行不存在" in str(exc_info.value.message), exc_info.value.message
    finally:
        conn.close()

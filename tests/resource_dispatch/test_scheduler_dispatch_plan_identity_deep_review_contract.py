"""回归测试：deep review 要求 partial 最新正式方案只能看，不能派工/写现场/导出复盘。"""

from __future__ import annotations

from pathlib import Path

from core.infrastructure.errors import ValidationError
from core.services.report import ReportEngine
from tests.resource_dispatch.test_scheduler_dispatch_plan_identity_guard import (
    VERSION,
    _dispatch_payload,
    _seed_db,
)


def test_partial_latest_official_plan_is_viewable_but_not_executable(tmp_path: Path) -> None:
    conn = _seed_db(tmp_path)
    try:
        conn.execute("UPDATE ScheduleHistory SET result_status = 'partial' WHERE version = ?", (VERSION,))
        conn.commit()

        data = _dispatch_payload(conn, version=VERSION)
        identity = data["plan_identity"]
        assert identity["can_dispatch"] is False
        assert identity["can_write_feedback"] is False
        assert identity["kind_label"] == "只能查看的方案"
        assert "部分成功" in identity["guardrail_text"]
        assert "不能当作当前可执行正式方案" in identity["guardrail_text"]
        try:
            ReportEngine(conn).export_execution_review_xlsx(VERSION)
        except ValidationError as exc:
            assert exc.field == "plan_identity"
            assert exc.details["reason"] == "not_reviewable_official_plan"
        else:
            raise AssertionError("partial 最新正式版本不能导出计划和现场实际")
    finally:
        conn.close()

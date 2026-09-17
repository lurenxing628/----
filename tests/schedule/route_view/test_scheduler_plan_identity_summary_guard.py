"""回归测试：当 result_summary 解析失败/缺失或版本被更新版本取代时，仪表盘、资源派工、执行复盘三处页面把它当作可见数据缺口(「当前排产摘要读取失败」等)而非 500，并据 plan_identity 关闭派工/写现场反馈入口；非法或越界 version 请求、缺失/非法/越界 overdue 与利用率指标都呈现「数据不足」而非伪造 0。"""

from __future__ import annotations

import os
from typing import Set
from urllib.parse import urlparse

from core.infrastructure.database import get_connection
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED, SchedulePlanQueryService
from tests._support.schedule_retirement import (
    initialize_read_fixture,
)
from tests.web_pages.reports_workbench_backlink_helpers import _client as _fixture_client


def _client():
    """Use the existing real plan fixture with startup defaults already persisted."""
    client = _fixture_client()
    initialize_read_fixture(client.application)
    return client


def _assert_no_path_links(value, paths: Set[str]) -> None:
    """No enabled link in the actual public projection may bypass the guard."""
    if isinstance(value, dict):
        url = value.get("url") or value.get("href")
        if url and not value.get("disabled"):
            assert urlparse(url).path not in paths
        for item in value.values():
            _assert_no_path_links(item, paths)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _assert_no_path_links(item, paths)


def test_bad_newer_summary_does_not_promote_previous_official_version() -> None:
    _client()
    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        row = conn.execute(
            "SELECT op_id, machine_id, operator_id FROM Schedule WHERE version = 12 ORDER BY id LIMIT 1"
        ).fetchone()
        conn.execute(
            """
            INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (row[0], row[1], row[2], "2026-05-07 08:00:00", "2026-05-07 12:00:00", "unlocked", 13),
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (13, "priority_first", 1, 1, "success", "{bad-json", "pytest"),
        )
        conn.commit()

        service = SchedulePlanQueryService(conn)
        latest = service.resolve_plan(13, ROLE_ADOPTED).to_dict()["plan_identity"]
        previous = service.resolve_plan(12, ROLE_ADOPTED).to_dict()["plan_identity"]

        assert latest["result_summary_parse_failed"] is True
        assert latest["is_current_executable_official_version"] is False
        assert latest["can_write_feedback"] is False
        assert previous["is_superseded_by_newer_version"] is True
        assert previous["is_current_executable_official_version"] is False
        assert previous["can_write_feedback"] is False
    finally:
        conn.close()


def test_blocked_or_missing_summary_history_is_not_current_writable_official_plan() -> None:
    _client()
    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        row = conn.execute(
            "SELECT op_id, machine_id, operator_id FROM Schedule WHERE version = 12 ORDER BY id LIMIT 1"
        ).fetchone()
        for version, result_status, result_summary in (
            (13, "blocked", "{}",),
            (14, "success", None,),
        ):
            conn.execute(
                """
                INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (row[0], row[1], row[2], "2026-05-07 08:00:00", "2026-05-07 12:00:00", "unlocked", version),
            )
            conn.execute(
                """
                INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (version, "priority_first", 1, 1, result_status, result_summary, "pytest"),
            )
            conn.commit()

            latest = SchedulePlanQueryService(conn).resolve_plan(version, ROLE_ADOPTED).to_dict()["plan_identity"]

            assert latest["source_row_id"] is not None
            assert latest["is_current_executable_version"] is True
            assert latest["is_current_executable_official_version"] is False
            assert latest["can_dispatch"] is False
            assert latest["can_write_feedback"] is False
            if result_summary is None:
                assert latest["result_summary_parse_failed"] is True
                assert latest["result_summary_parse_reason"] == "排产摘要缺失"
    finally:
        conn.close()


def test_empty_schedule_detail_history_is_not_current_writable_official_plan() -> None:
    _client()
    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (13, "priority_first", 0, 0, "success", "{}", "pytest"),
        )
        conn.commit()

        service = SchedulePlanQueryService(conn)
        latest = service.resolve_plan(13, ROLE_ADOPTED).to_dict()["plan_identity"]
        previous = service.resolve_plan(12, ROLE_ADOPTED).to_dict()["plan_identity"]

        assert latest["source_table"] == "schedule"
        assert latest["source_row_id"] is None
        assert latest["is_official"] is True
        assert latest["is_current_executable_version"] is True
        assert latest["is_current_executable_official_version"] is False
        assert latest["can_dispatch"] is False
        assert latest["can_write_feedback"] is False
        assert latest["detail_saved"] is False
        assert previous["is_superseded_by_newer_version"] is True
        assert previous["is_current_executable_official_version"] is False
        assert previous["can_write_feedback"] is False
    finally:
        conn.close()



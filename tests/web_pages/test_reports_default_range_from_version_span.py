"""回归测试：/reports/utilization 与 /reports/downtime 在缺省日期参数时，按所选版本（version=9）的排程范围自动带入 start_date/end_date。守护两个报表页都把日期回填为该版本 Schedule 的最早/最晚日（2099-01-10）、展示"已按所选版本的排程范围自动带入日期。"提示，即使 downtime 结果为空也照常带入范围。"""

from __future__ import annotations

from urllib.parse import unquote

from tests._support.legacy_report_contract import assert_retired, business_rows, get_unchanged, xlsx_text


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


def _assert_retained_range(client, db_path, version, dates):
    from core.infrastructure.database import get_connection
    from core.services.report import ReportEngine
    from web.routes.report_plan_preview import export_date_range_or_version_span

    before = business_rows(db_path)
    conn = get_connection(db_path)
    try:
        engine = ReportEngine(conn)
        assert export_date_range_or_version_span(engine, version, "adopted", None, "", "") == dates
        for build in (engine.utilization, engine.downtime_impact):
            report = build(version, *dates, enforce_date_range_limit=False)
            assert (report["start_date"], report["end_date"]) == dates
            if version == 9 and build == engine.downtime_impact:
                assert report["machines"] == []
    finally:
        conn.close()
    for name in ("utilization", "downtime"):
        export_path = f"/reports/{name}/export?version={version}&plan_role=adopted"
        response = get_unchanged(client, f"/reports/{name}?version={version}", db_path)
        assert_retired(response, public=(str(version), "正式采用方案"), downloads=(export_path,))
        exported = get_unchanged(client, export_path, db_path)
        if name == "downtime" and version == 9:
            assert exported.status_code == 400
            assert "暂无数据，不能导出" in exported.get_data(as_text=True)
            continue
        _assert_status(exported, export_path)
        filename = unquote(exported.headers["Content-Disposition"])
        assert dates[0] + "至" + dates[1] in filename
        text = xlsx_text(exported.data)
        if name == "utilization":
            assert ("MC_R1" if version == 9 else "MC_LONG_R1") in text
        elif version == 10:
            assert "MC_LONG_R1" in text
    assert business_rows(db_path) == before


def test_reports_default_range_from_version_span(app_client, db_path) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO Parts(part_no, part_name) VALUES (?, ?)", ("P_RANGE", "测试零件"))
        conn.execute("INSERT INTO Machines(machine_id, name, status) VALUES (?, ?, ?)", ("MC_R1", "测试设备", "active"))
        conn.execute("INSERT INTO Operators(operator_id, name, status) VALUES (?, ?, ?)", ("OP_R1", "测试人员", "active"))
        conn.execute(
            """
            INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_RANGE", "P_RANGE", "测试零件", 1, "2099-12-31", "normal", "yes", "pending", "range regression"),
        )
        conn.execute(
            """
            INSERT INTO BatchOperations(op_code, batch_id, seq, op_type_name, source, machine_id, operator_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_RANGE_10", "B_RANGE", 10, "数铣", "internal", "MC_R1", "OP_R1", 0.5, 1.0, "scheduled"),
        )
        row = conn.execute("SELECT id FROM BatchOperations WHERE op_code=?", ("B_RANGE_10",)).fetchone()
        if not row:
            raise RuntimeError("未插入 BatchOperations")
        op_id = int(row["id"])

        conn.execute(
            """
            INSERT INTO Schedule(op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (op_id, "MC_R1", "OP_R1", "2099-01-10 08:00:00", "2099-01-10 12:00:00", "unlocked", 9),
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (9, "test", 1, 1, "success", "{}", "regression"),
        )
        conn.commit()
    finally:
        conn.close()

    _assert_retained_range(app_client, db_path, 9, ("2099-01-10", "2099-01-10"))


def test_reports_version_span_longer_than_custom_limit_is_allowed(app_client, db_path) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO Parts(part_no, part_name) VALUES (?, ?)", ("P_LONG_RANGE", "长跨度零件"))
        conn.execute("INSERT INTO Machines(machine_id, name, status) VALUES (?, ?, ?)", ("MC_LONG_R1", "长跨度设备", "active"))
        conn.execute("INSERT INTO Operators(operator_id, name, status) VALUES (?, ?, ?)", ("OP_LONG_R1", "长跨度人员", "active"))
        conn.execute(
            """
            INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_LONG_RANGE", "P_LONG_RANGE", "长跨度零件", 1, "2099-12-31", "normal", "yes", "pending", "long range"),
        )
        conn.execute(
            """
            INSERT INTO BatchOperations(op_code, batch_id, seq, op_type_name, source, machine_id, operator_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_LONG_RANGE_10", "B_LONG_RANGE", 10, "数铣", "internal", "MC_LONG_R1", "OP_LONG_R1", 0.5, 1.0, "scheduled"),
        )
        row = conn.execute("SELECT id FROM BatchOperations WHERE op_code=?", ("B_LONG_RANGE_10",)).fetchone()
        if not row:
            raise RuntimeError("未插入 BatchOperations")
        op_id = int(row["id"])
        conn.execute(
            """
            INSERT INTO Schedule(op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (op_id, "MC_LONG_R1", "OP_LONG_R1", "2099-01-10 08:00:00", "2099-04-15 12:00:00", "unlocked", 10),
        )
        conn.execute(
            """
            INSERT INTO MachineDowntimes(machine_id, start_time, end_time, reason_code, reason_detail, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("MC_LONG_R1", "2099-04-15 10:00:00", "2099-04-15 11:00:00", "maintenance", "长跨度导出测试", "active"),
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (10, "test", 1, 1, "success", "{}", "regression"),
        )
        conn.commit()
    finally:
        conn.close()

    _assert_retained_range(app_client, db_path, 10, ("2099-01-10", "2099-04-15"))
    for name in ("utilization", "downtime"):
        rejected = get_unchanged(
            app_client,
            f"/reports/{name}/export?version=10&start_date=2099-01-10&end_date=2099-04-15",
            db_path,
        )
        assert rejected.status_code == 400
        assert "日期范围不能超过 62 天" in rejected.get_data(as_text=True)

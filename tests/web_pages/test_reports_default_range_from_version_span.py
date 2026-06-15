"""回归测试：/reports/utilization 与 /reports/downtime 在缺省日期参数时，按所选版本（version=9）的排程范围自动带入 start_date/end_date。守护两个报表页都把日期回填为该版本 Schedule 的最早/最晚日（2099-01-10）、展示"已按所选版本的排程范围自动带入日期。"提示，即使 downtime 结果为空也照常带入范围。"""

from __future__ import annotations


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


def _assert_contains(html: str, needle: str, name: str) -> None:
    if needle not in html:
        raise RuntimeError(f"{name} 未包含期望内容：{needle!r}")


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

    client = app_client

    # utilization：无日期参数时，应自动落到 version=9 的排程范围
    r = client.get("/reports/utilization?version=9")
    _assert_status(r, "GET /reports/utilization?version=9")
    util_html = r.data.decode("utf-8", errors="ignore")
    _assert_contains(util_html, 'name="start_date" value="2099-01-10"', "utilization start_date")
    _assert_contains(util_html, 'name="end_date" value="2099-01-10"', "utilization end_date")
    _assert_contains(util_html, "已按所选版本的排程范围自动带入日期。", "utilization hint")
    _assert_contains(util_html, "MC_R1", "utilization machine row")

    # downtime：同样应自动使用 version=9 的日期范围（即使结果为空）
    r = client.get("/reports/downtime?version=9")
    _assert_status(r, "GET /reports/downtime?version=9")
    dt_html = r.data.decode("utf-8", errors="ignore")
    _assert_contains(dt_html, 'name="start_date" value="2099-01-10"', "downtime start_date")
    _assert_contains(dt_html, 'name="end_date" value="2099-01-10"', "downtime end_date")
    _assert_contains(dt_html, "已按所选版本的排程范围自动带入日期。", "downtime hint")


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

    client = app_client

    r = client.get("/reports/utilization?version=10")
    _assert_status(r, "GET /reports/utilization?version=10")
    util_html = r.data.decode("utf-8", errors="ignore")
    _assert_contains(util_html, 'name="start_date" value="2099-01-10"', "long utilization start_date")
    _assert_contains(util_html, 'name="end_date" value="2099-04-15"', "long utilization end_date")
    _assert_contains(util_html, "已按所选版本的排程范围自动带入日期。", "long utilization hint")
    assert "utilization/export" in util_html
    assert "utilization/export?version=10&amp;start_date" not in util_html
    _assert_status(client.get("/reports/utilization/export?version=10"), "GET /reports/utilization/export?version=10")

    r = client.get("/reports/downtime?version=10")
    _assert_status(r, "GET /reports/downtime?version=10")
    dt_html = r.data.decode("utf-8", errors="ignore")
    _assert_contains(dt_html, 'name="start_date" value="2099-01-10"', "long downtime start_date")
    _assert_contains(dt_html, 'name="end_date" value="2099-04-15"', "long downtime end_date")
    assert "downtime/export" in dt_html
    assert "downtime/export?version=10&amp;start_date" not in dt_html
    _assert_status(client.get("/reports/downtime/export?version=10"), "GET /reports/downtime/export?version=10")

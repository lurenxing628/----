"""回归测试：ExternalGroupService.set_merge_mode 接受大小写混用的 merge_mode（如 "MERGED"），将其规范化为小写 "merged" 并落库到 ExternalGroups；且 merged 模式下组内 PartOperations 的 ext_days 必须被清空为 NULL。"""


def test_external_group_service_merge_mode_case_insensitive(schema_conn) -> None:

    from core.services.process.external_group_service import ExternalGroupService

    conn = schema_conn

    # 准备最小数据：Parts + PartOperations + ExternalGroups
    conn.execute(
        "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed) VALUES (?,?,?,?)",
        ("P001", "零件", "", "yes"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P001", 10, "外协A", "external", None, 2.0, "G001", 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P001", 11, "外协B", "external", None, 1.0, "G001", 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO ExternalGroups (group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id, remark)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("G001", "P001", 10, 11, "separate", None, None, None),
    )
    conn.commit()

    svc = ExternalGroupService(conn)

    # 关键：merge_mode 大小写混用时仍应被接受
    g = svc.set_merge_mode(group_id="G001", merge_mode="MERGED", total_days=3)
    assert g.merge_mode == "merged", f"merge_mode 未规范化：{g.merge_mode!r}"
    assert float(g.total_days or 0) == 3.0, f"total_days 写入异常：{g.total_days!r}"

    row = conn.execute("SELECT merge_mode, total_days FROM ExternalGroups WHERE group_id='G001'").fetchone()
    assert row["merge_mode"] == "merged", f"ExternalGroups.merge_mode 未落库为 merged：{row['merge_mode']!r}"
    assert float(row["total_days"] or 0) == 3.0, f"ExternalGroups.total_days 落库异常：{row['total_days']!r}"

    # merged 模式：组内工序 ext_days 必须被清空（置 NULL）
    rows = conn.execute("SELECT seq, ext_days FROM PartOperations WHERE part_no='P001' ORDER BY seq ASC").fetchall()
    for r in rows:
        assert r["ext_days"] is None, f"merged 模式下 ext_days 应为 NULL：seq={r['seq']} ext_days={r['ext_days']!r}"



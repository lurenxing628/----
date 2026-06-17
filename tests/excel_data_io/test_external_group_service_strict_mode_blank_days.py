"""回归测试：ExternalGroupService.set_merge_mode 在 strict_mode=True 且某工序 per_op_days 为空时，应抛出 ValidationError（field=ext_days_10）并保持原 PartOperations.ext_days 不被覆盖。"""


def test_external_group_service_strict_mode_blank_days(schema_conn) -> None:

    from core.infrastructure.errors import ValidationError
    from core.services.process.external_group_service import ExternalGroupService

    conn = schema_conn
    try:
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed) VALUES (?, ?, ?, ?)",
            ("P001", "零件", "", "yes"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P001", 10, "表处理", "external", None, 2.0, "G001", 0.0, 0.0, "active"),
        )
        conn.execute(
            """
            INSERT INTO ExternalGroups (group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("G001", "P001", 10, 10, "separate", None, None, None),
        )
        conn.commit()

        svc = ExternalGroupService(conn)
        try:
            svc.set_merge_mode(group_id="G001", merge_mode="separate", per_op_days={10: ""}, strict_mode=True)
        except ValidationError as e:
            assert e.field == "ext_days_10", f"strict_mode 字段名异常：{e.field!r}"
        else:
            raise AssertionError("strict_mode=True 时空 ext_days 应被拒绝")

        row = conn.execute("SELECT ext_days FROM PartOperations WHERE part_no=? AND seq=?", ("P001", 10)).fetchone()
        assert row is not None and abs(float(row["ext_days"] or 0.0) - 2.0) < 1e-9, (
            f"strict_mode 失败后不应覆盖 ext_days：{dict(row) if row else None!r}"
        )

    finally:
        conn.close()

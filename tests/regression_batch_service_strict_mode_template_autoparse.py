"""回归测试：BatchService 在 strict_mode 下建批遇路由解析失败时，应抛 ErrorCode.ROUTE_PARSE_ERROR 且不残留任何 Batches 行——守护 strict 建批的原子性（失败即整体回滚，不留半截批次）。"""


def test_batch_service_strict_mode_template_autoparse(schema_conn) -> None:

    from core.infrastructure.errors import BusinessError, ErrorCode
    from core.services.scheduler.batch_service import BatchService

    conn = schema_conn
    try:
        conn.execute(
            "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)",
            ("OT_EXT", "表处理", "external"),
        )
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
            ("P_ROUTE", "路线件", "10表处理", "no", None),
        )
        conn.commit()

        svc = BatchService(conn, logger=None, op_logger=None)
        try:
            svc.create_batch_from_template(
                batch_id="B_STRICT",
                part_no="P_ROUTE",
                quantity=1,
                priority="normal",
                ready_status="yes",
                strict_mode=True,
            )
        except BusinessError as e:
            assert e.code == ErrorCode.ROUTE_PARSE_ERROR, f"strict_mode 建批应返回 ROUTE_PARSE_ERROR：{e.code!r}"
        else:
            raise AssertionError("strict_mode=True 时自动补建模板应因缺供应商映射失败")

        row = conn.execute("SELECT COUNT(1) AS cnt FROM Batches WHERE batch_id=?", ("B_STRICT",)).fetchone()
        assert row is not None and int(row["cnt"] or 0) == 0, f"strict_mode 失败后不应残留 Batches：{dict(row) if row else None!r}"

    finally:
        conn.close()



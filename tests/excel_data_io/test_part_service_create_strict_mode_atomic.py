"""回归测试：PartService.create(strict_mode=True) 因路线解析失败（外协工序缺供应商映射）抛 ROUTE_PARSE_ERROR 后必须原子回滚，Parts 与 PartOperations 均不得残留半截数据。"""


def test_part_service_create_strict_mode_atomic(schema_conn) -> None:

    from core.infrastructure.errors import BusinessError, ErrorCode
    from core.services.process.part_service import PartService

    conn = schema_conn
    try:
        conn.execute(
            "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)",
            ("OT_EXT", "表处理", "external"),
        )
        conn.commit()

        svc = PartService(conn, logger=None, op_logger=None)

        try:
            svc.create(part_no="P_STRICT", part_name="严格件", route_raw="10表处理", strict_mode=True)
        except BusinessError as e:
            assert e.code == ErrorCode.ROUTE_PARSE_ERROR, f"严格创建应返回 ROUTE_PARSE_ERROR：{e.code!r}"
        else:
            raise AssertionError("strict_mode=True 时应因缺供应商映射而拒绝创建")

        row = conn.execute("SELECT COUNT(1) AS cnt FROM Parts WHERE part_no=?", ("P_STRICT",)).fetchone()
        assert row is not None and int(row["cnt"] or 0) == 0, f"strict_mode 失败后不应残留 Parts：{dict(row) if row else None!r}"

        op_row = conn.execute("SELECT COUNT(1) AS cnt FROM PartOperations WHERE part_no=?", ("P_STRICT",)).fetchone()
        assert op_row is not None and int(op_row["cnt"] or 0) == 0, f"strict_mode 失败后不应残留 PartOperations：{dict(op_row) if op_row else None!r}"

    finally:
        conn.close()



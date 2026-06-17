"""回归测试：PartService._save_template_no_tx 保存外协工序时若 default_days 为 0（无真实周期），ext_days 应回退为 1.0，ParseResult 状态降级为 PARTIAL，并透出"本次会先按 1 天记录，请补成真实周期"的 warning。"""

import sqlite3


def test_part_service_external_default_days_fallback(schema_conn) -> None:
    from core.services.process.part_service import PartService
    from core.services.process.route_parser import ExternalGroup, ParsedOperation, ParseResult, ParseStatus

    conn = schema_conn
    try:
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
            ("P001", "外协件", "10表处理", "yes", None),
        )
        conn.commit()

        svc = PartService(conn, logger=None, op_logger=None)
        parse_result = ParseResult(
            status=ParseStatus.SUCCESS,
            operations=[
                ParsedOperation(
                    seq=10,
                    op_type_name="表处理",
                    source="external",
                    supplier_id=None,
                    default_days=0.0,
                    ext_group_id="P001_EXT_1",
                    is_recognized=True,
                )
            ],
            external_groups=[
                ExternalGroup(
                    group_id="P001_EXT_1",
                    start_seq=10,
                    end_seq=10,
                    operations=[],
                )
            ],
            warnings=[],
            errors=[],
            stats={"total": 1, "internal": 0, "external": 1, "unknown": 0},
            original_input="10表处理",
            normalized_input="10表处理",
        )

        svc._save_template_no_tx(part_no="P001", parse_result=parse_result)

        row = conn.execute("SELECT ext_days FROM PartOperations WHERE part_no=? AND seq=?", ("P001", 10)).fetchone()
        assert row is not None, "PartOperations 未写入外部工序"
        ext_days = row["ext_days"] if isinstance(row, sqlite3.Row) else row[0]
        assert abs(float(ext_days or 0.0) - 1.0) < 1e-9, f"ext_days 未回退为 1.0：{ext_days!r}"
        assert parse_result.status in (ParseStatus.PARTIAL, ParseStatus.PARTIAL.value), f"保存期 fallback 后状态应为 PARTIAL：{parse_result.status!r}"
        assert any("本次会先按 1 天记录，请补成真实周期" in str(msg) for msg in (parse_result.warnings or [])), (
            f"未透出保存期 fallback warning：{parse_result.warnings!r}"
        )

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass

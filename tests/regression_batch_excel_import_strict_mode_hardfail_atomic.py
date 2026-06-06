"""回归测试：BatchService.import_from_preview_rows 在 strict_mode=True 且自动补建工序需要 route_parser fallback 时，应抛 BusinessError(ROUTE_PARSE_ERROR) 硬失败，且失败后 Batches/BatchOperations 无残留（原子回滚）。"""

from types import SimpleNamespace


def test_batch_excel_import_strict_mode_hardfail_atomic(schema_conn) -> None:

    from core.infrastructure.errors import BusinessError, ErrorCode
    from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
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
        preview_rows = [
            ImportPreviewRow(
                row_num=2,
                status=RowStatus.NEW,
                data={
                    "批次号": "B_STRICT_IMPORT",
                    "图号": "P_ROUTE",
                    "数量": 1,
                    "交期": "2026-06-01",
                    "优先级": "normal",
                    "齐套": "yes",
                    "齐套日期": None,
                    "备注": "strict-mode-hardfail",
                },
                message="将新增",
            )
        ]

        try:
            svc.import_from_preview_rows(
                preview_rows=preview_rows,
                mode=ImportMode.OVERWRITE,
                parts_cache={"P_ROUTE": SimpleNamespace(part_name="路线件")},
                auto_generate_ops=True,
                strict_mode=True,
                existing_ids=set(),
            )
        except BusinessError as e:
            assert e.code == ErrorCode.ROUTE_PARSE_ERROR, f"strict_mode Excel 导入应返回 ROUTE_PARSE_ERROR：{e.code!r}"
        else:
            raise AssertionError("strict_mode=True 且模板补建需要 fallback 时，Excel 导入应硬失败")

        batch_row = conn.execute("SELECT COUNT(1) AS cnt FROM Batches WHERE batch_id=?", ("B_STRICT_IMPORT",)).fetchone()
        assert batch_row is not None and int(batch_row["cnt"] or 0) == 0, (
            f"strict_mode 失败后不应残留 Batches：{dict(batch_row) if batch_row else None!r}"
        )

        op_row = conn.execute("SELECT COUNT(1) AS cnt FROM BatchOperations WHERE batch_id=?", ("B_STRICT_IMPORT",)).fetchone()
        assert op_row is not None and int(op_row["cnt"] or 0) == 0, (
            f"strict_mode 失败后不应残留 BatchOperations：{dict(op_row) if op_row else None!r}"
        )

    finally:
        conn.close()



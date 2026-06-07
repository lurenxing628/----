"""回归测试：BatchService.create_batch_from_template(strict_mode=True) 路由解析失败时的契约——
抛 ErrorCode.ROUTE_PARSE_ERROR 且 Batches 不残留任何行（失败即整体回滚，不留半截批次）。

两态契约：
- legacy_resolver_returns_none：注入 legacy resolver 返回 None，被拒并透出专属文案；
- autoparse_missing_supplier：默认 autoparse resolver，插 OpTypes 但缺供应商映射 → 失败。

合并自 regression_batch_service_legacy_template_resolver_rejects_strict_mode.py（legacy 分支）
与 regression_batch_service_strict_mode_template_autoparse.py（autoparse 分支）；
按 resolver 形态参数化，拒绝/失败的各自专属断言全部保留。
"""

import pytest


@pytest.mark.parametrize("case", ["legacy_resolver_returns_none", "autoparse_missing_supplier"])
def test_batch_service_strict_mode_template_rejects(schema_conn, case) -> None:
    from core.infrastructure.errors import BusinessError, ErrorCode
    from core.services.scheduler.batch_service import BatchService

    conn = schema_conn

    # 分支专属 setup：仅 autoparse 走到供应商映射，需要 OpTypes；
    # legacy resolver 直接返回 None，纯走拒绝路径，绝不可插 OpTypes（避免改变路径假设）。
    if case == "autoparse_missing_supplier":
        conn.execute(
            "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)",
            ("OT_EXT", "表处理", "external"),
        )
    conn.execute(
        "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
        ("P_ROUTE", "路线件", "10表处理", "no", None),
    )
    conn.commit()

    if case == "legacy_resolver_returns_none":
        def legacy_resolver(part_no, part_name, route_raw, no_tx):
            return None

        svc = BatchService(conn, template_resolver=legacy_resolver)
        batch_id = "B_STRICT_LEGACY"
    else:
        svc = BatchService(conn, logger=None, op_logger=None)
        batch_id = "B_STRICT"

    # pytest.raises 覆盖并加强原 autoparse 分支 try/except/else 的「必须抛异常」隐式断言。
    with pytest.raises(BusinessError) as exc_info:
        svc.create_batch_from_template(
            batch_id=batch_id,
            part_no="P_ROUTE",
            quantity=1,
            priority="normal",
            ready_status="yes",
            strict_mode=True,
        )

    err = exc_info.value
    assert err.code == ErrorCode.ROUTE_PARSE_ERROR, f"strict_mode 建批应返回 ROUTE_PARSE_ERROR：{err.code!r}"

    if case == "legacy_resolver_returns_none":
        # legacy 分支专属文案，autoparse case 无此断言（保真：不可去重）。
        assert "不支持“资料不完整就停下”" in err.message

    row = conn.execute(
        "SELECT COUNT(1) AS cnt FROM Batches WHERE batch_id=?", (batch_id,)
    ).fetchone()
    assert row is not None and int(row["cnt"] or 0) == 0, (
        f"strict_mode 失败后不应残留 Batches：{dict(row) if row else None!r}"
    )

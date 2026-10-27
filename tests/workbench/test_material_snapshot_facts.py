"""One read snapshot owns material rows, requirements and their projected records."""

from dataclasses import asdict

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_material_query import MaterialPageRequest
from core.services.workbench.material import queries
from core.services.workbench.material.queries import WorkbenchMaterialQueryService
from data.repositories.workbench_material_query_repo import _SELECT


def _seed(conn, rows):
    conn.executescript("""
        CREATE TABLE Materials(material_id TEXT PRIMARY KEY, name TEXT, spec TEXT, unit TEXT,
                               stock_qty REAL, status TEXT, remark TEXT);
        CREATE TABLE WorkbenchEntityRefs(ref TEXT PRIMARY KEY, kind TEXT, entity_key TEXT,
                                        revision INTEGER, active INTEGER);
        CREATE TABLE BatchMaterials(batch_id TEXT, material_id TEXT);
    """)
    for number, row in enumerate(rows, 1):
        conn.execute("INSERT INTO Materials VALUES (?, ?, ?, 'kg', ?, ?, NULL)", row)
        conn.execute("INSERT INTO WorkbenchEntityRefs VALUES (?, 'material', ?, 1, 1)",
                     (format(number, "048x"), row[0]))
    conn.executemany("INSERT INTO BatchMaterials VALUES (?, ?)",
                     [("B1", rows[0][0]), ("B2", rows[0][0]), ("B3", "orphan")])
    conn.commit()


def test_snapshot_reuses_raw_requirements_and_projected_rows_preserving_sqlite_scope(mem_conn, monkeypatch):
    _seed(mem_conn, [("M1", "Alpha", None, 5, "active"), ("M2", "ALPHA", "中文", 5, "inactive"),
                     ("M3", "Ä", None, None, "inactive"), ("M4", "ä", "中文", 3, "inactive"),
                     ("M5", None, "plain", 4, "active"), ("M6", b"\xffunmatched", b"aLPHa", 6, "active")])
    reader = WorkbenchMaterialQueryService(mem_conn)
    scopes = [MaterialPageRequest(sort="stock_qty"), MaterialPageRequest(sort="stock_qty", direction="desc"),
              MaterialPageRequest(query="aLPHa", status="active", sort="stock_qty", direction="desc"),
              MaterialPageRequest(query="ä"), MaterialPageRequest(query="中文"),
              MaterialPageRequest(sort="label"), MaterialPageRequest(sort="label", direction="desc")]
    expected = []
    for scope in scopes:
        rows, total = reader.repo.page(query=scope.query, status=scope.status, number=scope.number,
                                      size=scope.size, sort=scope.sort, direction=scope.direction)
        counts = reader.repo.metrics(scope.query, scope.status)
        # 仓储额外报出一条状态存坏的物料编号，交给服务拒绝；这里种子全部合法。
        assert counts.pop("damaged_code") is None
        expected.append(([asdict(queries._project(row)) for row in rows], total, counts))
    expected_fingerprint = {"state": reader.repo.snapshot_state(),
                            "rows": reader.repo.fetchall(_SELECT + " ORDER BY m.material_id")}
    statements, projected = [], []
    mem_conn.set_trace_callback(statements.append)
    original = queries._project

    def observed(row):
        projected.append(row["material_id"])
        return original(row)

    monkeypatch.setattr(queries, "_project", observed)
    with reader.read_snapshot() as fingerprint:
        assert fingerprint == expected_fingerprint
        assert {row["material_id"]: row["amount"] for row in fingerprint["state"]["requirements"]} == {
            "M1": 2, "orphan": 1}
        assert reader.state_fingerprint() is fingerprint
        for scope, (records, total, counts) in zip(scopes, expected):
            actual, page = reader.page(scope)
            assert [asdict(record) for record in actual] == records
            assert page["total"] == total and reader.metrics(scope)["counts"] == counts
        scope = MaterialPageRequest(sort="spec")
        facets = reader.facets(scope, "spec")
        assert facets["row_count"] == 6
        index = reader.table_index(scope)
        records, page = reader.page(scope)
        assert page["total"] == 6 and all(record.state["material"] is index.rows[record.identity.entity_key] for record in records)
        assert reader.matching_rows(scope) == [record.state["material"] for record in records]
        assert reader.facet_selection(scope, "spec")["total"] == len(facets["options"])
        filtered = MaterialPageRequest(column_filters={"status": {"mode": "include", "values": [index.cells["M1"]["status"].key]}})
        records, page = reader.page(filtered)
        assert [record.identity.entity_key for record in records] == ["M1", "M5", "M6"] and page["total"] == 3
        assert reader.metrics(filtered)["counts"] == {"total": 3, "active": 3, "inactive": 0, "stock_unknown": 0}
        assert reader.table_index(filtered) is index
    selects = [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 3
    assert sum("GROUP BY material_id" in sql for sql in selects) == 1
    assert not any("SELECT COUNT(*) FROM BatchMaterials AS b" in sql for sql in selects)
    assert sorted(projected) == ["M1", "M2", "M3", "M4", "M5", "M6"]
    assert reader._snapshot is None


@pytest.mark.parametrize("stored", [None, "legacy", " active", "ACTIVE"])
def test_damaged_material_status_is_rejected_as_storage_failure(mem_conn, stored):
    # 写入口只产出启用或停用；其他存储值不猜成启用或停用，整页读取直接报存储损坏。
    _seed(mem_conn, [("M1", "good", None, 1, "active"), ("M2", "damaged", None, 1, stored)])
    reader = WorkbenchMaterialQueryService(mem_conn)
    with reader.read_snapshot(), pytest.raises(WorkbenchCommandRejected) as error:
        reader.page(MaterialPageRequest())
    assert (error.value.code, error.value.status) == ("storage_failure", 500)


def test_ordinary_page_defers_unshown_bad_stock_and_nested_snapshot_is_restored(mem_conn):
    _seed(mem_conn, [("A", "shown", None, 1, "active"), ("Z", "unshown", None, -1, "active")])
    reader = WorkbenchMaterialQueryService(mem_conn)
    scope = MaterialPageRequest(size=1)
    with reader.read_snapshot() as fingerprint:
        records, page = reader.page(scope)
        assert records[0].entity["business_code"] == "A" and page["total"] == 2
        assert reader.toolbar_metrics(scope)["total"] == 2
        outer = reader._snapshot
        with reader.read_snapshot() as inner:
            assert inner == fingerprint and reader._snapshot is not outer
            bounded, _ = reader.page(MaterialPageRequest(query="shown", size=1))
            assert bounded[0].entity["business_code"] == "A"
        assert reader._snapshot is outer and reader.state_fingerprint() is fingerprint
        assert reader.page(scope)[0][0] is records[0]
        with pytest.raises(WorkbenchCommandRejected, match="库存数量"):
            reader.facets(scope, "stock_qty")
    assert reader._snapshot is None
    mem_conn.execute("UPDATE Materials SET stock_qty=2 WHERE material_id='Z'")
    mem_conn.commit()
    with reader.read_snapshot() as fresh:
        assert fresh != fingerprint
        assert reader.page(MaterialPageRequest(number=2, size=1))[0][0].entity["fields"]["stock_qty"] == 2

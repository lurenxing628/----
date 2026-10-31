"""One read snapshot owns material rows, requirements and their projected records."""

from dataclasses import asdict

from core.infrastructure.workbench_source_revisions_schema import (
    source_revisions_initialization_sql,
    source_revisions_objects,
)
from core.models.workbench_material_query import MaterialPageRequest
from core.services.workbench.facts.source_revisions import MATERIAL_SOURCE_KEYS, read_source_revisions
from core.services.workbench.material import queries
from core.services.workbench.material.files import WorkbenchMaterialFileService
from core.services.workbench.material.queries import WorkbenchMaterialQueryService
from data.repositories.workbench_material_query_repo import _SELECT


def _seed(conn, rows):
    ddl = source_revisions_objects()
    conn.executescript("""
        CREATE TABLE Materials(material_id TEXT PRIMARY KEY, name TEXT, spec TEXT, unit TEXT,
                               stock_qty REAL, status TEXT, remark TEXT, created_at TEXT);
        CREATE TABLE WorkbenchEntityRefs(ref TEXT PRIMARY KEY, kind TEXT, entity_key TEXT,
                                        revision INTEGER, active INTEGER);
        CREATE TABLE BatchMaterials(batch_id TEXT, material_id TEXT);
    """)
    conn.execute(ddl["WorkbenchSourceRevisions"])
    conn.execute(source_revisions_initialization_sql())
    conn.execute(ddl["wb_src_rev_materials_update"])
    for number, row in enumerate(rows, 1):
        conn.execute("INSERT INTO Materials VALUES (?, ?, ?, 'kg', ?, ?, NULL, NULL)", row)
        conn.execute("INSERT INTO WorkbenchEntityRefs VALUES (?, 'material', ?, 1, 1)",
                     (format(number, "048x"), row[0]))
    conn.executemany("INSERT INTO BatchMaterials VALUES (?, ?)",
                     [("B1", rows[0][0]), ("B2", rows[0][0]), ("B3", "orphan")])
    conn.commit()


def test_snapshot_reuses_raw_requirements_and_projected_rows_preserving_sqlite_scope(mem_conn, monkeypatch):
    _seed(mem_conn, [("M1", "Alpha", None, 5, "active"), ("M2", "ALPHA", "中文", 5, "inactive"),
                     ("M3", "Ä", None, None, "inactive"), ("M4", "ä", "中文", 3, "inactive"),
                     ("M5", None, "plain", 4, "active"), ("M6", "unmatched", "other", 6, "active")])
    reader = WorkbenchMaterialQueryService(mem_conn)
    scopes = [MaterialPageRequest(sort="stock_qty"), MaterialPageRequest(sort="stock_qty", direction="desc"),
              MaterialPageRequest(query="aLPHa", status="active", sort="stock_qty", direction="desc"),
              MaterialPageRequest(query="ä"), MaterialPageRequest(query="中文"),
              MaterialPageRequest(sort="label"), MaterialPageRequest(sort="label", direction="desc")]
    expected_rows = reader.repo.fetchall(_SELECT + " ORDER BY m.material_id")
    expected = []
    for scope in scopes:
        toolbar = queries.material_toolbar_rows(expected_rows, scope)
        ordered = queries.material_ordered_rows(toolbar, scope)
        start = (scope.number - 1) * scope.size
        rows = ordered[start:start + scope.size]
        counts = queries.material_counts(toolbar)
        expected.append(([asdict(queries._project(queries.material_row(row))) for row in rows], len(ordered), counts))
    expected_fingerprint = {"revisions": read_source_revisions(mem_conn, MATERIAL_SOURCE_KEYS)}
    statements, projected = [], []
    mem_conn.set_trace_callback(statements.append)
    original = queries._project

    def observed(row):
        projected.append(row.raw["material_id"])
        return original(row)

    monkeypatch.setattr(queries, "_project", observed)
    checked, original_check = [], queries.material_row

    def counted_check(raw):
        checked.append(raw["material_id"])
        return original_check(raw)

    monkeypatch.setattr(queries, "material_row", counted_check)
    with reader.read_snapshot() as fingerprint:
        assert fingerprint == expected_fingerprint
        assert reader._snapshot["rows"] is None
        assert reader.state_fingerprint() is fingerprint
        assert [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")] == [
            sql for sql in statements if "WorkbenchSourceRevisions" in sql
        ]
        for scope, (records, total, counts) in zip(scopes, expected):
            actual, page = reader.page(scope)
            assert [asdict(record) for record in actual] == records
            assert page["total"] == total and reader.metrics(scope)["counts"] == counts
        assert reader._snapshot["rows"] == expected_rows
        scope = MaterialPageRequest(sort="spec")
        facets = reader.facets(scope, "spec")
        assert facets["row_count"] == 6
        index = reader.table_index(scope)
        records, page = reader.page(scope)
        # 表格查询的分页和导出直接复用索引里已过存储校验的同一份物料行。
        assert page["total"] == 6 and all(record.state["material"] is index.rows[record.identity.entity_key].raw for record in records)
        assert reader.matching_rows(scope) == [index.rows[record.identity.entity_key] for record in records]
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
    # 七次普通分页、筛选项、表格索引、导出行和列筛选分页共用快照内同一次存储校验。
    assert sorted(checked) == ["M1", "M2", "M3", "M4", "M5", "M6"]
    assert reader._snapshot is None


def test_ordinary_page_defers_unshown_bad_stock_and_nested_snapshot_is_restored(mem_conn):
    _seed(mem_conn, [("A", "shown", None, 1, "active"), ("Z", "unshown", None, 0, "active")])
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
    assert reader._snapshot is None
    mem_conn.execute("UPDATE Materials SET stock_qty=2 WHERE material_id='Z'")
    mem_conn.commit()
    with reader.read_snapshot() as fresh:
        assert fresh != fingerprint
        statements = []
        mem_conn.set_trace_callback(statements.append)
        try:
            assert WorkbenchMaterialFileService(mem_conn, reader=reader).export_rows("csv", selected_refs=[]) == []
        finally:
            mem_conn.set_trace_callback(None)
        assert not any("FROM Materials" in sql for sql in statements)
        assert reader._snapshot["rows"] is None
        detail = reader.detail(format(2, "048x"))
        assert detail.entity["business_code"] == "Z" and reader._snapshot["rows"] is None
        exported = WorkbenchMaterialFileService(mem_conn, reader=reader).export_rows(
            "csv", selected_refs=[format(2, "048x")]
        )
        assert reader._snapshot["rows"] is None
        assert [row["business_code"] for row in exported] == ["Z"] and exported[0]["stock_qty"] == 2
        assert reader.page(MaterialPageRequest(number=2, size=1))[0][0].entity["fields"]["stock_qty"] == 2
        assert reader._snapshot["rows"] is not None

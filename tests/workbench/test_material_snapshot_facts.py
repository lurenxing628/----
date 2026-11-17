"""Bounded SQL pagination and snapshot reuse for material queries."""

from dataclasses import asdict

import pytest

from core.infrastructure.sqlite_udf import text_sort_key_for_sql
from core.infrastructure.workbench_source_revisions_schema import (
    source_revisions_initialization_sql,
    source_revisions_objects,
)
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_material_query import MaterialPageRequest
from core.services.workbench.facts.source_revisions import MATERIAL_SOURCE_KEYS, read_source_revisions
from core.services.workbench.material import queries
from core.services.workbench.material.files import WorkbenchMaterialFileService
from core.services.workbench.material.queries import WorkbenchMaterialQueryService
from core.services.workbench.material.table_facts import material_row
from data.repositories.sqlite_rows import sql_order
from data.repositories.workbench_material_query_repo import _SELECT

_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
_BYTE_LOWER = bytes.maketrans(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ", b"abcdefghijklmnopqrstuvwxyz")
_SORT_FIELDS = {"business_code": "material_id", "label": "name", "spec": "spec", "stock_qty": "stock_qty", "status": "status"}
_TEXT_SORTS = ("business_code", "label", "spec")


def _material_toolbar_rows(rows, query):
    """Match the existing SQLite toolbar: ASCII lower, NULL exclusion, exact status."""
    needle = query.query.translate(_ASCII_LOWER)
    byte_needle = needle.encode("utf-8")

    def matches(value):
        if value is None:
            return False
        if isinstance(value, bytes):
            return byte_needle in value.translate(_BYTE_LOWER)
        return needle in value.translate(_ASCII_LOWER)

    return [
        row
        for row in rows
        if (query.status is None or row["status"] == query.status)
        and (not needle or any(matches(row[field]) for field in ("material_id", "name", "spec")))
    ]


def _material_ordered_rows(rows, query):
    """Captured raw rows are already business-code ASC; stable sorting keeps that tie order.
    Text columns sort by the normalized text key, like the text cells."""
    field = _SORT_FIELDS[query.sort]
    return sorted(
        rows,
        key=lambda row: sql_order(text_sort_key_for_sql(row[field]) if query.sort in _TEXT_SORTS else row[field]),
        reverse=query.direction == "desc",
    )


def _material_counts(rows):
    statuses = [row["status"] for row in rows]
    return {"total": len(rows), "active": statuses.count("active"), "inactive": statuses.count("inactive"),
            "stock_unknown": sum(row["stock_qty"] is None for row in rows)}


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


def test_snapshot_sql_pagination_and_table_index_preserve_sqlite_scope(mem_conn, monkeypatch):
    _seed(mem_conn, [("M1", "Alpha", None, 5, "active"), ("M2", "ALPHA", "中文", 5, "inactive"),
                     ("M3", "Ä", None, None, "inactive"), ("M4", "ä", "中文", 3, "inactive"),
                     ("M5", None, "plain", 4, "active"), ("M6", "unmatched", "other", 6, "active")])
    reader = WorkbenchMaterialQueryService(mem_conn)
    assert not hasattr(reader.repo, "table_rows")
    scopes = [
        MaterialPageRequest(sort="stock_qty", size=2, number=1),
        MaterialPageRequest(sort="stock_qty", size=2, number=2),
        MaterialPageRequest(sort="stock_qty", direction="desc"),
        MaterialPageRequest(query="aLPHa", status="active", sort="stock_qty", direction="desc"),
        MaterialPageRequest(query="ä"),
        MaterialPageRequest(query="中文"),
        MaterialPageRequest(sort="label"),
        MaterialPageRequest(sort="label", direction="desc"),
    ]
    expected_rows = reader.repo.fetchall(_SELECT + " ORDER BY m.material_id")
    expected = []
    for scope in scopes:
        toolbar = _material_toolbar_rows(expected_rows, scope)
        ordered = _material_ordered_rows(toolbar, scope)
        start = (scope.number - 1) * scope.size
        rows = ordered[start : start + scope.size]
        counts = _material_counts(toolbar)
        expected.append(([asdict(queries._project(material_row(row))) for row in rows], len(ordered), counts))
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
    try:
        with reader.read_snapshot() as snapshot:
            assert not hasattr(snapshot, "_ensure_rows")
            fingerprint = snapshot.state_fingerprint()
            assert fingerprint == expected_fingerprint
            assert snapshot.state_fingerprint() is fingerprint
            assert [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")] == [
                sql for sql in statements if "WorkbenchSourceRevisions" in sql
            ]
            for scope, (records, total, counts) in zip(scopes, expected):
                actual, page = snapshot.page(scope)
                assert [asdict(record) for record in actual] == records
                assert page["total"] == total and snapshot.metrics(scope)["counts"] == counts
            scope = MaterialPageRequest(sort="spec")
            facets = snapshot.facets(scope, "spec")
            assert facets["row_count"] == 6
            index = snapshot.table_index(scope)
            records, page = snapshot.page(scope)
            assert page["total"] == 6 and all(
                record.state["material"] is index.rows[record.identity.entity_key].raw for record in records
            )
            assert snapshot.matching_rows(scope) == [index.rows[record.identity.entity_key] for record in records]
            assert snapshot.facet_selection(scope, "spec")["total"] == len(facets["options"])
            filtered = MaterialPageRequest(
                column_filters={"status": {"mode": "include", "values": [index.cells["M1"]["status"].key]}}
            )
            records, page = snapshot.page(filtered)
            assert [record.identity.entity_key for record in records] == ["M1", "M5", "M6"] and page["total"] == 3
            assert snapshot.metrics(filtered)["counts"] == {
                "total": 3,
                "active": 3,
                "inactive": 0,
                "stock_unknown": 0,
            }
            assert snapshot.table_index(filtered) is index
    finally:
        mem_conn.set_trace_callback(None)
    assert not any("SELECT COUNT(*) FROM BatchMaterials AS b" in sql for sql in statements)
    assert sorted(projected) == ["M1", "M2", "M3", "M4", "M5", "M6"]
    assert sorted(checked) == ["M1", "M2", "M3", "M4", "M5", "M6"]


def test_ordinary_page_defers_unshown_bad_stock_and_nested_snapshot_is_restored(mem_conn):
    _seed(mem_conn, [("A", "shown", None, 1, "active"), ("Z", "unshown", None, -1, "active")])
    reader = WorkbenchMaterialQueryService(mem_conn)
    scope = MaterialPageRequest(size=1)
    with reader.read_snapshot() as outer:
        fingerprint = outer.state_fingerprint()
        records, page = outer.page(scope)
        assert records[0].entity["business_code"] == "A" and page["total"] == 2
        assert outer.metrics(scope)["counts"]["total"] == 2
        with reader.read_snapshot() as inner:
            assert inner is not outer and inner.state_fingerprint() == fingerprint
            bounded, _ = inner.page(MaterialPageRequest(query="shown", size=1))
            assert bounded[0].entity["business_code"] == "A"
        assert outer.state_fingerprint() is fingerprint
        assert outer.page(scope)[0][0] is records[0]
        with pytest.raises(WorkbenchCommandRejected) as exc_info:
            outer.page(MaterialPageRequest(number=2, size=1))
        assert exc_info.value.code == "storage_failure"
    mem_conn.execute("UPDATE Materials SET stock_qty=2 WHERE material_id='Z'")
    mem_conn.commit()
    file_service = WorkbenchMaterialFileService(mem_conn)
    with reader.read_snapshot() as fresh:
        assert fresh.state_fingerprint() != fingerprint
        statements = []
        mem_conn.set_trace_callback(statements.append)
        try:
            assert file_service.export_rows(fresh, "csv", selected_refs=[]) == []
            assert not any("FROM Materials" in sql for sql in statements)
            detail = fresh.detail(format(2, "048x"))
            assert detail.entity["business_code"] == "Z"
            assert not any("LIMIT 1 OFFSET 1" in sql for sql in statements)
            exported = file_service.export_rows(fresh, "csv", selected_refs=[format(2, "048x")])
            assert [row["business_code"] for row in exported] == ["Z"] and exported[0]["stock_qty"] == 2
            assert fresh.page(MaterialPageRequest(number=2, size=1))[0][0].entity["fields"]["stock_qty"] == 2
            assert sum("LIMIT 1 OFFSET 1" in sql for sql in statements) == 1
        finally:
            mem_conn.set_trace_callback(None)

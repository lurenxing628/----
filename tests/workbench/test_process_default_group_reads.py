"""Route imports reuse supplier defaults and skip catalog reads for internal work."""

from core.infrastructure.transaction import TransactionManager
from core.services.workbench.process.file_codec import encode_process_file
from core.services.workbench.process.files import WorkbenchProcessFileService
from core.services.workbench.process.group_defaults import apply_default_groups
from tests.workbench.process_commands_support import stage_database

_stage_fixture = stage_database


def test_internal_route_does_not_load_supplier_defaults(stage_conn):
    def unexpected(*_args, **_kwargs):
        raise AssertionError("Internal operations do not consume supplier defaults.")

    assert not apply_default_groups(stage_conn, "PROC-001", [10, 30], catalog_reader=unexpected)


def test_route_file_shares_one_current_supplier_catalog(stage_conn, monkeypatch, record_property):
    from core.services.workbench.process import file_route

    conn = stage_conn
    conn.execute("INSERT INTO WorkbenchOpTypePolicies(op_type_id,default_merge_mode) VALUES ('PROC-EX','merged')")
    conn.commit()
    rows = [{"business_code": code, "label": "新增零件", "route_raw": "10热处理20热处理"}
            for code in ("DEFAULT-01", "DEFAULT-02")]
    content = encode_process_file("route", rows, "csv").content
    service = WorkbenchProcessFileService(conn)
    preview, _ = service.preview_import("route", content, file_format="csv")
    assert all(not row["errors"] for row in preview.as_dict()["rows"]), preview.as_dict()["rows"]
    reads, original = [], file_route.default_suppliers

    def catalog(references):
        reads.append(True)
        return original(references)

    monkeypatch.setattr(file_route, "default_suppliers", catalog)
    with TransactionManager(conn).transaction(begin_immediate=True):
        outcome = service.confirm_import(preview, content, discard_group_refs=[], confirm_zero_unit_hours=False)
    assert outcome.result == "committed" and len(reads) == 1
    groups = conn.execute("SELECT part_no,start_seq,end_seq,total_days FROM ExternalGroups WHERE part_no LIKE 'DEFAULT-%' ORDER BY part_no").fetchall()
    assert [tuple(row) for row in groups] == [("DEFAULT-01", 10, 20, 4.5), ("DEFAULT-02", 10, 20, 4.5)]
    record_property("default_supplier_catalog_builds", len(reads))

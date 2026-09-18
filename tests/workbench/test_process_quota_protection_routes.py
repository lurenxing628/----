"""Route replacements never transfer locks; stale imports never bind replacements."""



from core.infrastructure.transaction import TransactionManager
from core.services.process.part_service import PartService
from core.services.workbench.process_file_codec import encode_process_file
from core.services.workbench.process_files import WorkbenchProcessFileService
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from core.services.workbench.process_quota_protection import ProcessQuotaProtection
from tests.workbench.process_commands_support import run_stage, source_input
from tests.workbench.process_quota_protection_support import (
    adopt,
    assert_rejected,
    snapshot,
    templates,
)
from tests.workbench.process_quota_protection_support import locked_quota_case as _locked  # noqa: F401
from tests.workbench.process_quota_protection_support import quota_case as _quota  # noqa: F401
from tests.workbench.template_lineage_support import ledger_fixture as _ledger  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage  # noqa: F401


def test_same_workbench_template_route_edit_keeps_quota_blob_and_lock(locked_quota_case):
    case = locked_quota_case
    old = templates(case.conn)[1]
    identity = WorkbenchProcessQueryService(case.conn).resolve(case.ref("part", "P1"))
    payload = {"route": {"mode": "rows", "rows": [{"seq": 1, "op_type_name": "Renamed"},
               {"seq": 2, "op_type_name": "Turning"}]}, "discard_group_refs": []}
    result = run_stage(case.conn, "route_confirm", payload, identity=identity)
    assert result["result"] == "committed"
    new = templates(case.conn)[1]
    assert new == {**old, "op_type_name": "Renamed"}
    assert ProcessQuotaProtection(case.conn).bind("P1", 1) == case.template_ref
    assert_rejected("calibration_quota_locked", lambda: PartService(case.conn).update_internal_hours("P1", 1, 0, 99))


def test_source_switch_keeps_hidden_locked_quota_on_the_same_ref(locked_quota_case):
    case = locked_quota_case
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES('E1','Coating','external')")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES('S1','Supplier','E1')")
    case.conn.commit()
    identity = WorkbenchProcessQueryService(case.conn).resolve(case.ref("part", "P1"))
    original = source_input(case.conn, "P1")
    external = source_input(case.conn, "P1")
    external["operations"][0].update(source="external", op_type_ref=case.ref("op_type", "E1"),
                                     supplier_ref=case.ref("supplier", "S1"))
    run_stage(case.conn, "source_confirm", external, identity=identity, key="cw-source-switch-external")
    assert templates(case.conn)[1]["source"] == "external" and templates(case.conn)[1]["unit_hours"] == 3
    run_stage(case.conn, "source_confirm", original, identity=identity, key="cw-source-switch-internal")
    assert ProcessQuotaProtection(case.conn).bind("P1", 1) == case.template_ref
    assert_rejected("calibration_quota_locked", lambda: PartService(case.conn).update_internal_hours("P1", 1, 0, 99))


def test_workbench_file_coordinator_rejects_stale_preview_instead_of_rebinding(quota_case):
    case = quota_case
    content = encode_process_file("hours", [{"business_code": "P1", "sequence": 1, "unit_hours": 99},
        {"business_code": "P1", "sequence": 2, "unit_hours": 8}], "xlsx").content
    svc = WorkbenchProcessFileService(case.conn)
    preview, _ = svc.preview_import("hours", content, file_format="xlsx")
    adopt(case)
    before = snapshot(case.conn)
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        assert_rejected("stale_write", lambda: svc.confirm_import(preview, content,
            discard_group_refs=[], confirm_zero_unit_hours=False))
    assert snapshot(case.conn) == before



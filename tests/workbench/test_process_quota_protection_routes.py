"""Route replacements never transfer locks; stale imports never bind replacements."""

import json

import pytest
from flask import g

from core.infrastructure.transaction import TransactionManager
from core.services.common.excel_templates import build_xlsx_bytes
from core.services.process.part_operation_hours_excel_import_service import PartOperationHoursExcelImportService
from core.services.process.part_service import PartService
from core.services.workbench.process_file_codec import encode_process_file
from core.services.workbench.process_files import WorkbenchProcessFileService
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from core.services.workbench.process_quota_protection import ProcessQuotaProtection
from data.repositories.workbench_calibration_adoption_repo import WorkbenchCalibrationAdoptionRepository
from tests.workbench.process_commands_support import run_stage, source_input
from tests.workbench.process_quota_protection_support import (
    adopt,
    assert_rejected,
    file_apply,
    file_preview,
    legacy_preview,
    snapshot,
    templates,
)
from tests.workbench.process_quota_protection_support import locked_quota_case as _locked  # noqa: F401
from tests.workbench.process_quota_protection_support import quota_case as _quota  # noqa: F401
from tests.workbench.test_template_lineage_support import ledger_fixture as _ledger  # noqa: F401
from tests.workbench.test_template_lineage_support import lineage_case as _lineage  # noqa: F401
from web.routes import process_excel_part_operation_hours as legacy_routes
from web.routes.helpers.excel_utils import encode_preview_rows_payload


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


@pytest.mark.parametrize("entry", ["reparse", "route_import"])
def test_explicit_new_template_semantics_remain_allowed_and_locks_do_not_transfer(locked_quota_case, entry):
    case = locked_quota_case
    rows, _ = file_preview(case.conn, {"sequence": 1, "unit_hours": 99})
    legacy = legacy_preview(case.conn, {"工序": 1, "单件工时(h)": 99})
    before = snapshot(case.conn)
    svc = PartService(case.conn)
    if entry == "reparse":
        svc.reparse_and_save("P1", "1Turning2Turning")
    else:
        with TransactionManager(case.conn).transaction(begin_immediate=True):
            svc.upsert_and_parse_no_tx("P1", "Part", "1Turning2Turning")
    current_ref = ProcessQuotaProtection(case.conn).bind("P1", 1)
    assert current_ref != case.template_ref
    locks = WorkbenchCalibrationAdoptionRepository(case.conn).read_locks([current_ref, case.template_ref])
    assert set(locks) == {case.template_ref} and templates(case.conn)[1]["unit_hours"] == 3
    after_replacement = snapshot(case.conn)
    assert_rejected("stale_write", lambda: file_apply(case.conn, rows))
    assert_rejected("stale_write", lambda: PartOperationHoursExcelImportService(case.conn).apply_preview_rows(legacy))
    assert snapshot(case.conn) == after_replacement
    svc.update_internal_hours("P1", 1, 0, 8)
    assert templates(case.conn)[1]["unit_hours"] == 8
    for table in ("Batches", "BatchOperations", "Schedule", "ScheduleHistory", "WorkbenchCalibrationAdoptions",
                  "WorkbenchCalibrationQuotaLocks", "WorkbenchExecutionReportRevisions"):
        if table in before:
            assert snapshot(case.conn)[table] == before[table], table


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


def _legacy_upload(case, monkeypatch):
    monkeypatch.setattr(legacy_routes, "_render_excel_part_op_hours_page", lambda **kwargs: kwargs)
    content = build_xlsx_bytes(["图号", "工序", "换型时间(h)", "单件工时(h)"], [["P1", 1, 9, 99], ["P1", 2, 0.5, 8]])
    with case.app.test_request_context("/preview", method="POST", data={"mode": "overwrite", "file": (content, "hours.xlsx")}):
        g.db = case.conn
        return legacy_routes.excel_part_op_hours_preview()


def _legacy_confirm(case, preview):
    payload = encode_preview_rows_payload(preview["raw_rows_json"])
    with case.app.test_request_context("/confirm", method="POST", data={"mode": "overwrite", "filename": "hours.xlsx",
        "raw_rows_json": payload, "preview_baseline": preview["preview_baseline"]}):
        g.db = case.conn
        return legacy_routes.excel_part_op_hours_confirm()


def test_old_excel_real_upload_and_confirm_share_locked_skips(locked_quota_case, monkeypatch):
    case = locked_quota_case
    case.app.add_url_rule("/hours", "process.excel_part_op_hours_page", lambda: "hours")
    preview = _legacy_upload(case, monkeypatch)
    assert preview["preview_rows"][0].status.value == "skip"
    assert preview["preview_rows"][0].data["quota_skip"]["template_operation_ref"] == case.template_ref
    assert json.loads(preview["raw_rows_json"])[0]["template_operation_ref"] == case.template_ref
    before = templates(case.conn)
    result = _legacy_confirm(case, preview)
    assert result.status_code == 302
    assert templates(case.conn) == {1: before[1], 2: {**before[2], "unit_hours": 8}}


@pytest.mark.parametrize("change", ["adopt", "replace"])
def test_old_excel_baseline_binds_lock_and_ref_even_when_business_values_unchanged(quota_case, monkeypatch, change):
    case = quota_case
    preview = _legacy_upload(case, monkeypatch)
    if change == "adopt":
        adopt(case)
    else:
        PartService(case.conn).reparse_and_save("P1", "1Turning2Turning")
    before = snapshot(case.conn)
    result = _legacy_confirm(case, preview)
    assert result["preview_rows"] is None and result["preview_baseline"] is None
    assert snapshot(case.conn) == before

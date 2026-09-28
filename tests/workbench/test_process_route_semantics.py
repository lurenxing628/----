"""Route edits preserve readable names and reconcile actual work-type choices."""

import pytest

from core.models.process_route_text import serialize_route_rows
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.part_service import PartService
from core.services.process.route_parser import ParseStatus, RouteParser
from core.services.process.workflow_state import read_workflow
from core.services.workbench.process.queries import WorkbenchProcessQueryService
from core.services.workbench.process.route_preview import ProcessRoutePreviewService
from data.repositories.op_type_repo import OpTypeRepository
from data.repositories.supplier_repo import SupplierRepository
from tests.workbench.process_commands_support import (
    hours_input,
    identity_for,
    op_rows,
    route_input,
    run_stage,
    source_input,
    storage,
)
from tests.workbench.process_commands_support import stage_database as _stage_fixture  # noqa: F401
from tests.workbench.process_quota_protection_support import locked_quota_case as _locked  # noqa: F401
from tests.workbench.process_quota_protection_support import quota_case as _quota  # noqa: F401
from tests.workbench.template_lineage_support import ledger_fixture as _ledger  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage  # noqa: F401


@pytest.mark.parametrize("name", ["3D打印", "CNC3", "Heat treatment", "镀层;检验", '镀层"复检', "车削\n检验", "3轴、精加工"])
def test_structured_names_roundtrip_through_both_route_parsers(stage_conn, name):
    stage_conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('EXPLICIT-NAME',?,'internal')", (name,))
    stage_conn.commit()
    text = serialize_route_rows([(10, name), (20, "检验")])
    result = ProcessRoutePreviewService(stage_conn).preview({"mode": "text", "route_raw": text})
    assert result["can_confirm_route"]
    assert [(row["sequence"], row["op_type_name"]) for row in result["operations"]] == [(10, name), (20, "检验")]
    parser = RouteParser(OpTypeRepository(stage_conn), SupplierRepository(stage_conn))
    assert parser.validate_format(text)[0]
    legacy = parser.parse(text, "NEW", strict_mode=True)
    assert legacy.status == ParseStatus.SUCCESS
    assert [(row.seq, row.op_type_name) for row in legacy.operations] == [(10, name), (20, "检验")]
    service = PartService(stage_conn)
    service.create("EXPLICIT-PART", "可逆路线", route_raw=text)
    assert [(row["seq"], row["op_type_name"]) for row in stage_conn.execute(
        "SELECT seq,op_type_name FROM PartOperations WHERE part_no='EXPLICIT-PART' ORDER BY seq")] == [(10, name), (20, "检验")]
    reparsed = service.reparse_and_save("EXPLICIT-PART", text, strict_mode=True)
    assert [(row.seq, row.op_type_name) for row in reparsed.operations] == [(10, name), (20, "检验")]


@pytest.mark.parametrize("text", ['10: "未结束', '10: "车削"多余', '10: 车削；20检验', '10: 车削；10: 检验', '0: 车削', '10: '])
def test_incomplete_explicit_routes_fail_without_guessing(stage_conn, text):
    before = storage(stage_conn)
    result = ProcessRoutePreviewService(stage_conn).preview({"mode": "text", "route_raw": text})
    assert not result["can_confirm_route"]
    parser = RouteParser(OpTypeRepository(stage_conn), SupplierRepository(stage_conn))
    assert not parser.validate_format(text)[0]
    assert parser.parse(text, "NEW").status == ParseStatus.FAILED
    assert storage(stage_conn) == before


def test_compact_numeric_name_ambiguity_is_rejected_instead_of_guessing(stage_conn):
    text = "103D打印20检验"
    assert ProcessRoutePreviewService(stage_conn).preview({"mode": "text", "route_raw": text})["can_confirm_route"]
    stage_conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('PRINT3D','3D打印','internal')")
    stage_conn.commit()
    preview = ProcessRoutePreviewService(stage_conn).preview({"mode": "text", "route_raw": text})
    assert not preview["can_confirm_route"]
    assert any(row["code"] == "ambiguous_numeric_name" and "10: 3D打印" in row["message"] for row in preview["diagnostics"])
    parser = RouteParser(OpTypeRepository(stage_conn), SupplierRepository(stage_conn))
    assert parser.parse(text, "NEW").status == ParseStatus.FAILED
    for explicit in ("10: 3D打印；20: 检验", "103: D打印；20: 检验"):
        assert ProcessRoutePreviewService(stage_conn).preview({"mode": "text", "route_raw": explicit})["can_confirm_route"]


@pytest.mark.parametrize("member_days", [3.25, None, -1, "坏旧值"])
def test_retained_merged_route_preview_uses_effective_group_total(stage_conn, member_days):
    stage_conn.execute("UPDATE PartOperations SET ext_days=? WHERE part_no='PROC-001' AND seq=20", (member_days,))
    stage_conn.commit()
    body = route_input(stage_conn)
    reader = WorkbenchProcessQueryService(stage_conn)
    preview = reader.route_difference(identity_for(stage_conn).ref, ProcessRoutePreviewService(stage_conn).preview(body["route"]))
    operation = preview["operations"][1]
    assert operation["external_days"] == 6.75
    assert "统一周期计算一次" in operation["basis"]
    assert not any(issue["code"] in ("value_invalid", "value_missing") for issue in operation["issues"])


def test_route_preview_explains_cycle_after_explicit_group_discard(stage_conn):
    body = route_input(stage_conn, "10: 车削；20: 热处理备注；30: 检验")
    reader = WorkbenchProcessQueryService(stage_conn)
    preview = reader.route_difference(identity_for(stage_conn).ref, ProcessRoutePreviewService(stage_conn).preview(body["route"]))
    operation = preview["operations"][1]
    assert operation["external_days"] == 3.25
    assert "解除原外协段" in operation["basis"]


def test_renaming_to_another_registered_type_applies_preview_not_old_binding(stage_conn):
    old = op_rows(stage_conn)[10]
    body = route_input(stage_conn, "10: 热处理；20: 热处理；30: 检验")
    reader = WorkbenchProcessQueryService(stage_conn)
    preview = reader.route_difference(identity_for(stage_conn).ref, ProcessRoutePreviewService(stage_conn).preview(body["route"]))
    proposed = preview["operations"][0]
    assert proposed["source_suggestion"] == "external"
    assert "0.5" in proposed["basis"] and "0.125" in proposed["basis"]
    run_stage(stage_conn, "route_confirm", body, key="route-change-known-type-01")
    after = op_rows(stage_conn)[10]
    assert (after["id"], after["private_legacy"], after["created_at"]) == (old["id"], old["private_legacy"], old["created_at"])
    assert after["op_type_id"] == "PROC-EX" and after["source"] == "external"
    assert after["setup_hours"] is None and after["unit_hours"] is None
    entity = WorkbenchProcessQueryService(stage_conn).detail(identity_for(stage_conn).ref)
    assert entity["operations"][0]["supplier_ref"] == proposed["supplier_ref"]
    assert entity["operations"][0]["external_days"] == proposed["external_days"]
    run_stage(stage_conn, "source_confirm", source_input(stage_conn), key="route-change-known-type-02")
    run_stage(stage_conn, "hours_confirm", hours_input(stage_conn), key="route-change-known-type-03")
    assert read_workflow(stage_conn, "PROC-001")["ready"]
    assert op_rows(stage_conn)[10]["source"] == "external"


def test_switching_between_internal_types_does_not_reuse_old_hours(stage_conn):
    body = route_input(stage_conn, "10: 检验；20: 热处理；30: 检验")
    run_stage(stage_conn, "route_confirm", body, key="route-change-internal-type-01")
    operation = op_rows(stage_conn)[10]
    assert operation["op_type_id"] == "PROC-Q" and operation["source"] == "internal"
    assert operation["setup_hours"] is None and operation["unit_hours"] is None
    run_stage(stage_conn, "source_confirm", source_input(stage_conn), key="route-change-internal-type-02")
    assert not read_workflow(stage_conn, "PROC-001")["ready"]
    with pytest.raises(WorkbenchCommandRejected):
        run_stage(stage_conn, "hours_confirm", hours_input(stage_conn), key="route-change-internal-type-03")


@pytest.mark.parametrize("label", ["车削", "车削准备及备注"])
def test_unmodified_or_unregistered_labels_preserve_manual_binding_in_preview(stage_conn, label):
    stage_conn.execute("UPDATE PartOperations SET op_type_id='PROC-Q' WHERE part_no='PROC-001' AND seq=10")
    stage_conn.commit()
    old = op_rows(stage_conn)[10]
    body = route_input(stage_conn, serialize_route_rows([(10, label), (20, "热处理"), (30, "检验")]))
    preview = WorkbenchProcessQueryService(stage_conn).route_difference(identity_for(stage_conn).ref,
        ProcessRoutePreviewService(stage_conn).preview(body["route"]))
    assert "检验" in preview["operations"][0]["basis"] and "保留" in preview["operations"][0]["basis"]
    run_stage(stage_conn, "route_confirm", body, key="route-retain-manual-known-01")
    assert op_rows(stage_conn)[10] == {**old, "op_type_name": label}


def test_locked_calibration_quota_blocks_type_replacement_in_preview_and_write(locked_quota_case):
    conn = locked_quota_case.conn
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('NEW-TYPE','New machining','internal')")
    conn.commit()
    body = {"route": {"mode": "rows", "rows": [{"seq": 1, "op_type_name": "New machining"}, {"seq": 2, "op_type_name": "Turning"}]}, "discard_group_refs": []}
    identity = WorkbenchProcessQueryService(conn).resolve(locked_quota_case.ref("part", "P1"))
    before = storage(conn)
    preview = WorkbenchProcessQueryService(conn).route_difference(identity.ref, ProcessRoutePreviewService(conn).preview(body["route"]))
    assert not preview["can_confirm_route"]
    assert any(row["code"] == "calibration_quota_locked" for row in preview["diagnostics"])
    with pytest.raises(WorkbenchCommandRejected):
        run_stage(conn, "route_confirm", body, key="route-locked-quota-01", identity=identity)
    assert storage(conn) == before

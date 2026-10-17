"""Route changes require acknowledgement before discarding an outsourcing group."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.process.mutations import WorkbenchProcessMutationService
from core.services.workbench.process.queries import WorkbenchProcessQueryService
from tests.workbench.process_commands_support import (
    group_rows,
    identity_for,
    op_ref,
    op_rows,
    ref_for,
    route_input,
    run_stage,
    stage_database,
    storage,
)
from tests.workbench.process_route_support import read_only_probe

_stage_fixture = stage_database


def test_route_review_reuses_current_facts_for_parser_and_choices(stage_conn, monkeypatch):
    from core.services.workbench.process.queries import WorkbenchProcessQueryService
    from core.services.workbench.process.route_preview import ProcessRoutePreviewService
    from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository

    calls = []
    original = ProcessRoutePreviewService.preview

    def parse(service, body):
        calls.append(body)
        return original(service, body)

    def reread(*args, **kwargs):
        raise AssertionError("route references must come from current process facts")

    monkeypatch.setattr(ProcessRoutePreviewService, "preview", parse)
    monkeypatch.setattr(WorkbenchProcessQueryRepository, "op_type_reference_rows", reread)
    monkeypatch.setattr(WorkbenchProcessQueryRepository, "supplier_reference_rows", reread)
    reader = WorkbenchProcessQueryService(stage_conn)
    with reader.read_snapshot():
        preview, _, affected = reader.prepare_route(identity_for(stage_conn).ref,
                                                    {"mode": "text", "route_raw": "10车削30检验"})
    assert len(calls) == 1 and preview["can_confirm_route"]
    assert [row["ref"] for row in affected] == [ref_for(stage_conn, "template_external_group", "PROC-G")]


def test_catalog_workflow_reuses_operation_states_and_preserves_stage_results(stage_conn, monkeypatch):
    from core.infrastructure.transaction import TransactionManager
    from core.services.process import workflow_state
    from tests.workbench.process_commands_support import prepare_stages

    prepare_stages(stage_conn)
    with TransactionManager(stage_conn).transaction():
        raw = workflow_state.load_workflow_snapshot(stage_conn)
    expected = {part["part_no"]: {
        "workflow": workflow_state.read_workflow(stage_conn, part["part_no"]),
        "operations": workflow_state.operation_confirmations(stage_conn, part["part_no"]),
    } for part in raw["parts"]}
    calls, original = [], workflow_state._operation_states

    def once(per_op, records, stored=None):
        calls.append(stored)
        return original(per_op, records, stored)

    monkeypatch.setattr(workflow_state, "_operation_states", once)
    assert workflow_state.project_workflow_snapshot(raw) == expected
    assert len(calls) == len(raw["parts"])


@pytest.mark.parametrize("change", ("remove",))
def test_group_impact_is_readonly_and_exact_ack_is_required(stage_conn, change):
    if change in ("insert_in_range", "restore"):
        stage_conn.execute("UPDATE ExternalGroups SET end_seq=25 WHERE group_id='PROC-G'")
    if change == "restore":
        stage_conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,source,status,ext_group_id) VALUES ('PROC-001',25,'历史','external','deleted','PROC-G')")
    stage_conn.commit()
    text = {"remove": "10车削30检验", "rename": "10车削20改名30检验", "insert_in_range": "10车削20热处理25新序30检验", "restore": "10车削20热处理25历史30检验"}[change]
    payload = route_input(stage_conn, text)
    del payload["discard_group_refs"]
    before = storage(stage_conn)
    service = WorkbenchProcessMutationService(stage_conn)
    reader = WorkbenchProcessQueryService(stage_conn)
    with reader.read_snapshot():
        checked = service.checked_facts(reader.resolve(identity_for(stage_conn).ref), reader.facts())
        normalized = service.normalize("route_confirm", payload)
        with read_only_probe(stage_conn):
            prepared = service.prepare_review("route_confirm", normalized, checked, facts=reader.facts())
        affected = sorted(row["ref"] for row in prepared.affected)
    assert affected == [ref_for(stage_conn, "template_external_group", "PROC-G")] and storage(stage_conn) == before
    for acknowledgement in ([],):
        with pytest.raises(WorkbenchCommandRejected):
            run_stage(stage_conn, "route_confirm", {**payload, "discard_group_refs": acknowledgement})
        assert storage(stage_conn) == before
    old, old_ref = op_rows(stage_conn), op_ref(stage_conn, 20)
    run_stage(stage_conn, "route_confirm", {**payload, "discard_group_refs": affected})
    assert group_rows(stage_conn) == {}
    assert op_rows(stage_conn)[20] == {**old[20], "ext_group_id": None,
        **({"status": "deleted"} if change == "remove" else {"op_type_name": "改名"} if change == "rename" else {})}
    assert op_ref(stage_conn, 20) == old_ref

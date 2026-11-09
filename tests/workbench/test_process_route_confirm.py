"""Route changes require acknowledgement before discarding an outsourcing group."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.process.mutations import WorkbenchProcessMutationService
from core.services.workbench.process.queries import WorkbenchProcessQueryService
from tests.workbench.process_commands_support import (
    group_rows,
    hours_input,
    identity_for,
    op_ref,
    op_rows,
    prepare_stages,
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
    identity = identity_for(stage_conn)
    assert identity is not None
    reader = WorkbenchProcessQueryService(stage_conn, part_ref=identity.ref)
    with reader.read_snapshot():
        facts = reader.facts()
        assert [row["part_no"] for row in facts["parts"]] == ["PROC-001"]
        assert {row["part_no"] for row in facts["operations"]} == {"PROC-001"}
        assert {row["part_no"] for row in facts["groups"]} == {"PROC-001"}
        assert set(facts["workflow"]) == {"PROC-001"}
        monkeypatch.setattr(WorkbenchProcessQueryRepository, "references", reread)
        monkeypatch.setattr(WorkbenchProcessQueryRepository, "identities", reread)
        preview, _, affected = reader.prepare_route(identity,
                                                    {"mode": "text", "route_raw": "10车削30检验"})
        mixed_preview, _, _ = reader.prepare_route(identity,
                                                   {"mode": "text", "route_raw": "10车削20:热处理"})
    assert len(calls) == 2 and preview["can_confirm_route"]
    assert not mixed_preview["can_confirm_route"]
    assert "explicit_route_invalid" in {row["code"] for row in mixed_preview["diagnostics"]}
    assert [row["ref"] for row in affected] == [ref_for(stage_conn, "template_external_group", "PROC-G")]


def test_catalog_workflow_reuses_operation_states_and_preserves_stage_results(stage_conn, monkeypatch):
    from core.infrastructure.transaction import TransactionManager
    from core.services.process import workflow_state

    prepare_stages(stage_conn)
    with TransactionManager(stage_conn).transaction():
        raw = workflow_state.load_workflow_snapshot(stage_conn)
        expected = {}
        for row in raw["parts"]:
            part, stored = workflow_state._part(stage_conn, row["part_no"])
            facts = workflow_state._facts(part, workflow_state._load_facts(stage_conn, row["part_no"]), stored)
            expected[row["part_no"]] = {
                "workflow": workflow_state._view(stored, facts),
                "operations": workflow_state._operation_states(facts[2], facts[3], stored),
            }
    calls, original = [], workflow_state._operation_states

    def once(per_op, records, stored=None):
        calls.append(stored)
        return original(per_op, records, stored)

    monkeypatch.setattr(workflow_state, "_operation_states", once)
    assert workflow_state.project_workflow_snapshot(raw) == expected
    assert len(calls) == len(raw["parts"])


def test_master_workflow_reuses_catalog_identity_index(stage_conn, monkeypatch):
    from core.infrastructure.transaction import TransactionManager
    from core.services.process.workflow_state import workflow_snapshot
    from core.services.workbench.master.overview_facts import MasterOverviewFacts

    prepare_stages(stage_conn)
    with TransactionManager(stage_conn).transaction():
        expected = workflow_snapshot(stage_conn)
    facts, scans = MasterOverviewFacts(stage_conn), []
    original = facts.repo.overview_tables

    class IdentityRows(list):
        def __iter__(self):
            scans.append(None)
            return super().__iter__()

    def capture(present):
        tables = original(present)
        tables["WorkbenchEntityRefs"] = IdentityRows(tables["WorkbenchEntityRefs"])
        return tables

    monkeypatch.setattr(facts.repo, "overview_tables", capture)
    with facts.read_snapshot():
        assert facts.workflow == expected
    assert len(scans) == 1


def test_group_impact_is_readonly_and_exact_ack_is_required(stage_conn):
    payload = route_input(stage_conn, "10车削30检验")
    del payload["discard_group_refs"]
    before = storage(stage_conn)
    service = WorkbenchProcessMutationService(stage_conn)
    reader = WorkbenchProcessQueryService(stage_conn)
    with reader.read_snapshot():
        identity = identity_for(stage_conn)
        assert identity is not None
        checked = service.checked_facts(reader.resolve(identity.ref), reader.facts())
        normalized = service.normalize("route_confirm", payload)
        with read_only_probe(stage_conn):
            prepared = service.prepare_review("route_confirm", normalized, checked, facts=reader.facts())
        affected = sorted(row["ref"] for row in prepared.affected)
    assert affected == [ref_for(stage_conn, "template_external_group", "PROC-G")] and storage(stage_conn) == before
    with pytest.raises(WorkbenchCommandRejected):
        run_stage(stage_conn, "route_confirm", {**payload, "discard_group_refs": []})
    assert storage(stage_conn) == before
    old, old_ref = op_rows(stage_conn), op_ref(stage_conn, 20)
    run_stage(stage_conn, "route_confirm", {**payload, "discard_group_refs": affected})
    assert group_rows(stage_conn) == {}
    assert op_rows(stage_conn)[20] == {**old[20], "ext_group_id": None, "status": "deleted"}
    assert op_ref(stage_conn, 20) == old_ref


def test_hours_confirm_with_external_and_zero_unit_hours_acknowledgement(stage_conn):
    prepare_stages(stage_conn)
    payload = hours_input(stage_conn)
    unacknowledged = {**payload, "confirm_zero_unit_hours": False}
    with pytest.raises(WorkbenchCommandRejected) as exc:
        run_stage(stage_conn, "hours_confirm", unacknowledged, key="hours-zero-unconfirmed")
    assert exc.value.code == "zero_unit_hours_confirmation_required"
    assert exc.value.status == 422
    assert exc.value.operation_refs == [op_ref(stage_conn, 30)]

    confirmed = run_stage(stage_conn, "hours_confirm", payload, key="hours-zero-confirmed")
    assert confirmed["result"] == "committed"

    repeated = run_stage(stage_conn, "hours_confirm", unacknowledged, key="hours-zero-unchanged")
    assert repeated["result"] == "unchanged"


def test_text_and_rows_route_inputs_preserve_padded_operation_name_and_bound_choices(schema_conn):
    schema_conn.executemany(
        "INSERT INTO OpTypes(op_type_id, name, category) VALUES (?, ?, 'internal')",
        [("OT-A", "A"), ("OT-B", "B")],
    )
    schema_conn.execute(
        "INSERT INTO Parts(part_no, part_name, route_raw, route_parsed) VALUES ('PROC-001', '轴套', NULL, 'no')"
    )
    schema_conn.commit()

    run_stage(
        schema_conn,
        "route_confirm",
        {"route": {"mode": "text", "route_raw": '10: " A "'}, "discard_group_refs": []},
        key="route-padded-init",
    )
    op_b_ref = ref_for(schema_conn, "op_type", "OT-B")
    run_stage(
        schema_conn,
        "source_confirm",
        {
            "operations": [
                {
                    "ref": op_ref(schema_conn, 10),
                    "source": "internal",
                    "op_type_ref": op_b_ref,
                    "supplier_ref": None,
                    "confirmed": True,
                }
            ],
            "discard_group_refs": [],
        },
        key="source-padded-bind-b",
    )
    run_stage(
        schema_conn,
        "hours_confirm",
        {
            "operations": [{"ref": op_ref(schema_conn, 10), "setup_hours": 1.5, "unit_hours": 0.25}],
            "groups": [],
            "confirm_zero_unit_hours": False,
        },
        key="hours-padded-fill",
    )

    identity = identity_for(schema_conn)
    reader = WorkbenchProcessQueryService(schema_conn, part_ref=identity.ref)
    text_route = {"mode": "text", "route_raw": '10: " A "'}
    rows_route = {"mode": "rows", "rows": [{"seq": 10, "op_type_name": " A "}]}
    for key_suffix, route_body in (("text", text_route), ("rows", rows_route)):
        with reader.read_snapshot():
            preview, _, affected = reader.prepare_route(identity, route_body)
        assert affected == []
        assert preview["can_confirm_route"] is True
        assert preview["route_raw"] == '10: " A "'
        assert preview["normalized_input"] == '10: " A "'
        assert preview["changes"] == {"added": [], "removed": [], "retained": [10], "same_sequence_changed": []}
        op_preview, = preview["operations"]
        assert op_preview["op_type_name"] == " A "
        assert op_preview["op_type_ref"] == op_b_ref
        assert op_preview["replace_existing_choices"] is False

        outcome = run_stage(
            schema_conn,
            "route_confirm",
            {"route": route_body, "discard_group_refs": []},
            key=f"route-padded-reconfirm-{key_suffix}",
        )
        assert outcome["result"] == "unchanged"
        persisted = op_rows(schema_conn)[10]
        assert persisted["op_type_name"] == " A "
        assert persisted["op_type_id"] == "OT-B"
        assert persisted["source"] == "internal"
        assert (persisted["setup_hours"], persisted["unit_hours"]) == (1.5, 0.25)

"""Real plan-chain reuse, original identities, strict scoped visibility and no writes."""

import json

import pytest

from core.services.scheduler.gantt_critical_chain import compute_critical_chain_from_rows
from core.services.workbench import actual_gantt_chain
from tests.workbench.final_execution_cases import final_e_runtime as final_e_runtime
from tests.workbench.final_execution_chain_seed import chain_plan
from tests.workbench.final_execution_seed import execution
from tests.workbench.final_execution_support import restart_preserved, serving
from tests.workbench.live_environment import write_json
from tests.workbench.report_execution_ledger_support import report_ledger_api as report_ledger_api
from tests.workbench.run_live_server_support import database_state

BASE = "/api/workbench/v1/actual-gantt"


def read(api, query, status=200, related=False):
    response = api.client.get(BASE + ("/chain" if related else ""), query_string=query)
    assert response.status_code == status, response.get_json()
    return response.get_json()


def test_real_factory_original_engine_three_edge_kinds_and_exact_minute_units(report_ledger_api, tmp_path):
    api = report_ledger_api
    seed = chain_plan(api)
    before = database_state(api.path)
    result = read(api, {"plan_ref": seed["plan_ref"]})
    chain = result["data"]["critical_chain"]
    assert chain["state"] == "available" and chain["partial"] is False
    assert chain["task_refs"] == seed["task_refs"][:4]
    assert chain["snapshot_ref"] == result["meta"]["snapshot_ref"]
    assert chain["plan_ref"] == seed["plan_ref"] and chain["scope"] == "full_plan"
    assert chain["gap_unit"] == "minute" and chain["gap_rounding"] == "floor"
    assert chain["makespan_end"] == "2026-09-09T13:00:00"
    assert [edge["edge_type"] for edge in chain["edges"]] == seed["expected_edge_types"]
    assert [edge["gap_minutes"] for edge in chain["edges"]] == seed["expected_gap_minutes"]
    with api.db() as conn:
        rows = [dict(row) for row in conn.execute("SELECT s.id AS schedule_id,s.start_time,s.end_time,s.machine_id,s.operator_id,"
            "o.op_code,o.batch_id,o.seq,o.piece_id,o.op_type_name FROM Schedule s JOIN BatchOperations o ON o.id=s.op_id WHERE version=1")]
    original = compute_critical_chain_from_rows(rows)
    assert original["ids"] == ["OP1", "CHAIN-OP2", "CHAIN-OP3", "CHAIN-OP4"]
    assert [edge["reason"] for edge in chain["edges"]] == [edge["reason"] for edge in original["edges"]]
    assert database_state(api.path) == before
    write_json(tmp_path / "original-engine-proof.json", {"response": result, "original_engine_output": original, "strict_changed_tables": []})


def test_scope_does_not_recompute_full_plan_chain_and_content_change_invalidates_token(report_ledger_api, tmp_path):
    api = report_ledger_api
    seed = chain_plan(api)
    original = read(api, {"plan_ref": seed["plan_ref"]})
    scoped = read(api, {"plan_ref": seed["plan_ref"], "batch_ids": json.dumps(["CHAIN-B2"])})
    first, narrowed = original["data"]["critical_chain"], scoped["data"]["critical_chain"]
    assert narrowed["task_refs"] == first["task_refs"] and narrowed["edges"] == first["edges"]
    assert narrowed["engine_evidence_ref"] == first["engine_evidence_ref"]
    assert narrowed["visible_node_count"] == 1
    assert [row["task_ref"] for row in narrowed["nodes"] if row["in_scope"]] == [seed["task_refs"][2]]
    with api.db() as conn:
        conn.execute("UPDATE Schedule SET end_time='2026-09-09 13:15:00' WHERE version=1 AND op_id=?", (seed["operation_ids"][3],))
    after_edit = database_state(api.path)
    failed = read(api, {"plan_ref": seed["plan_ref"], "snapshot_ref": original["meta"]["snapshot_ref"]}, 409)
    assert failed["error"]["code"] == "snapshot_stale"
    refreshed = read(api, {"plan_ref": seed["plan_ref"]})["data"]["critical_chain"]
    assert refreshed["task_refs"] == first["task_refs"] and refreshed["makespan_end"] == "2026-09-09T13:15:00"
    assert refreshed["engine_evidence_ref"] != first["engine_evidence_ref"]
    assert database_state(api.path) == after_edit
    write_json(tmp_path / "plan-chain-scope-and-drift.json", {"original": original, "scoped": scoped, "stale": failed, "refreshed": refreshed})


def test_mixed_common_piece_dependencies_are_explicitly_unsupported_not_fake_chain(report_ledger_api):
    api = report_ledger_api
    seed = execution(api)
    before = database_state(api.path)
    chain = read(api, {"plan_ref": seed["plan_ref"]})["data"]["critical_chain"]
    assert chain["state"] == "unavailable" and chain["reason_code"] == "engine_piece_precedence_unsupported"
    assert chain["nodes"] == chain["task_refs"] == chain["edges"] == []
    assert database_state(api.path) == before


def test_real_engine_result_corruption_is_rejected_not_presented_as_verified(report_ledger_api, monkeypatch):
    api = report_ledger_api
    seed = chain_plan(api)
    before = database_state(api.path)

    def corrupted(rows, *, target_id=None):
        result = compute_critical_chain_from_rows(rows, target_id=target_id)
        result["edges"][0]["gap_minutes"] = 999
        return result

    monkeypatch.setattr(actual_gantt_chain, "compute_critical_chain_from_rows", corrupted)
    chain = read(api, {"plan_ref": seed["plan_ref"]})["data"]["critical_chain"]
    assert chain["state"] == "unavailable" and chain["reason_code"] == "chain_engine_unavailable"
    assert database_state(api.path) == before


@pytest.mark.parametrize("invalid", [None, [], "invalid", 1])
def test_non_dictionary_engine_result_is_explicit_unavailable(report_ledger_api, monkeypatch, invalid):
    api = report_ledger_api
    seed = chain_plan(api)
    before = database_state(api.path)
    monkeypatch.setattr(actual_gantt_chain, "compute_critical_chain_from_rows", lambda *_args, **_kwargs: invalid)
    chain = read(api, {"plan_ref": seed["plan_ref"]})["data"]["critical_chain"]
    assert chain["state"] == "unavailable" and chain["engine_reason"] == "invalid_result_type"
    assert database_state(api.path) == before


def test_related_non_global_endpoint_uses_all_rows_and_original_snapshot(report_ledger_api, monkeypatch, tmp_path):
    api = report_ledger_api
    seed = chain_plan(api)
    seen = []

    def observe(rows, *, target_id=None):
        seen.append({"ids": [row["op_code"] for row in rows], "target": target_id})
        return compute_critical_chain_from_rows(rows, target_id=target_id)

    monkeypatch.setattr(actual_gantt_chain, "compute_critical_chain_from_rows", observe)
    before = database_state(api.path)
    initial = read(api, {"plan_ref": seed["plan_ref"]})
    base = {"plan_ref": seed["plan_ref"], "snapshot_ref": initial["meta"]["snapshot_ref"]}
    independent = read(api, dict(base, target_task_ref=seed["task_refs"][4]), related=True)
    chain = independent["data"]["critical_chain"]
    assert seed["task_refs"][4] not in initial["data"]["critical_chain"]["task_refs"]
    assert chain["task_refs"] == [seed["task_refs"][4]] and chain["edges"] == []
    assert chain["mode"] == "related" and chain["target_task_ref"] == seed["task_refs"][4]
    assert chain["snapshot_ref"] == initial["meta"]["snapshot_ref"]
    assert chain["engine_evidence_ref"] != initial["data"]["critical_chain"]["engine_evidence_ref"]
    cross_resource = read(api, dict(base, target_task_ref=seed["task_refs"][2]), related=True)
    assert cross_resource["data"]["critical_chain"]["task_refs"] == seed["task_refs"][:3]
    assert [row["edge_type"] for row in cross_resource["data"]["critical_chain"]["edges"]] == ["process", "machine"]
    assert seen and all(len(row["ids"]) == 5 for row in seen)
    assert {row["target"] for row in seen} == {None, "CHAIN-OP5", "CHAIN-OP3"}
    unknown = read(api, dict(base, target_task_ref="f" * 48), related=True)["data"]["critical_chain"]
    assert unknown["state"] == "unavailable" and unknown["reason_code"] == "chain_target_not_found"
    assert unknown["target_task_ref"] == "f" * 48 and unknown["task_refs"] == []
    missing = read(api, {"plan_ref": seed["plan_ref"], "target_task_ref": seed["task_refs"][0]}, 400, related=True)
    assert missing["error"]["code"] == "snapshot_required"
    assert database_state(api.path) == before
    write_json(tmp_path / "related-chain-proof.json", {"global": initial, "independent": independent, "cross_resource": cross_resource, "engine_calls": seen})


@pytest.mark.parametrize("kind,reason", [("unknown", "target_not_found"), ("zero", "target_time_unavailable"),
                                         ("duplicate", "target_identity_conflict"), ("empty", "target_invalid")])
def test_explicit_core_target_guards_keep_default_none_legacy_contract(kind, reason):
    row = {"op_code": "A", "batch_id": "B", "seq": 1, "start_time": "2026-09-09 08:00:00", "end_time": "2026-09-09 09:00:00"}
    rows, target = [row], "A"
    if kind == "unknown":
        target = "missing"
    elif kind == "zero":
        row["end_time"] = row["start_time"]
    elif kind == "duplicate":
        rows.append(dict(row))
    else:
        target = ""
    implicit = compute_critical_chain_from_rows(rows)
    assert implicit == compute_critical_chain_from_rows(rows, target_id=None)
    assert implicit.get("available", True) is True
    result = compute_critical_chain_from_rows(rows, target_id=target)
    assert result["available"] is False and result["reason_code"] == reason
    assert result["ids"] == result["edges"] == []


def test_full_main_computed_chain_interactions_and_real_restart(final_e_runtime):
    parent, built, runtime = final_e_runtime
    with serving(parent, built, runtime, "chain") as host:
        print("FINAL_CHAIN_ROOT " + str(host.root), flush=True)
        before = host.state()
        host.browser("final_execution_chain.cjs")
        initial = json.loads((host.root / "final-chain-initial.json").read_text(encoding="utf-8"))
        assert all(row["passed"] for row in initial["actions"])
        assert initial["gaps"] == initial["page_errors"] == initial["console_errors"] == initial["external_requests"] == []
        assert host.state() == before
        host.stop()
        host.start(reuse=True)
        restarted = host.state()
        audit = restart_preserved(before, restarted)
        host.browser("final_execution_chain.cjs", "restart")
        final = json.loads((host.root / "final-chain-restart.json").read_text(encoding="utf-8"))
        assert final["chain"]["engine_evidence_ref"] == initial["chain"]["engine_evidence_ref"]
        assert final["chain"]["nodes"] == initial["chain"]["nodes"]
        assert host.state() == restarted
        write_json(host.root / "final-chain-proof.json", {"initial": initial["actions"], "restart": final["actions"],
            "engine_evidence_ref": final["chain"]["engine_evidence_ref"], "strict_changed_tables": [], "restart_audit": audit})

"""Decision baselines use captured last-per-operation arrangements and identities."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from core.infrastructure.snapshot_connection import ddl_columns
from core.infrastructure.transaction import TransactionManager
from core.models.scheduler_history_parser import parse_result_summary_payload
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch.materials import WorkbenchBatchMaterialService
from core.services.workbench.facts.candidate_facts import _table
from core.services.workbench.facts.candidate_read_source import read_candidate_source
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.decision_baseline import (
    _last_official_rows,
    read_decision_baseline,
    read_decision_baseline_members,
)
from core.services.workbench.facts.decision_baseline_source import (
    _operation_metadata,
    decision_baseline_source_resolver,
)
from core.services.workbench.facts.zero_duration_evidence import CandidatePointReader
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.run_candidate_adoption_support import INTENT, service
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401


def _run(case, key, *batches, _expected_state="complete", **settings):
    accepted = case.accept(key="decision-baseline-run-" + key, settings=case.settings(*batches, **settings))
    run = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert run["state"] == _expected_state, run
    return read_candidate_source(CandidateStore(case.conn), run["candidates"][0]["candidate_ref"])


def _adopt(case, key, *batches, **settings):
    source = _run(case, key, *batches, **settings)
    ref = source.candidate["candidate_ref"]
    adopter = service(case.conn)
    adopter.point_rendering_enabled = True
    checked = adopter.preview(ref)
    assert checked["validation"]["can_adopt"], checked
    outcome = adopter.adopt(ref, checked["write_context"]["write_token"], "decision-baseline-adopt-" + key, INTENT)
    assert outcome["result"] == "committed", outcome
    return outcome["data"]["official_plan"], source


def _read(source, resolver=None):
    return read_decision_baseline(source.capture, source.facts, source.disposition, source.run["accepted_at"],
                                  source_resolver=resolver)


def _resolver(originals, calls):
    """Use already read immutable candidates; no current entity or plan reads."""
    def resolve(*, plan_ref, version, history):
        calls.append((plan_ref, version))
        source = originals.get(version)
        if source is None:
            return {"evidence": None}
        audit = parse_result_summary_payload(history["result_summary"]).payload
        reader = CandidatePointReader(source.candidate, source.facts)
        work = {row["payload"]["op_id"]: reader.work(row["operation_ref"], row["payload"])
                for row in source.raw_tasks if row["payload"]["start_time"] == row["payload"]["end_time"]}
        origins = {source.facts.operations[row["operation_ref"]]: {
            key: row[key] for key in ("source", "supplier", "machine", "operator", "data_gaps")}
            for row in source.tasks}
        return {"evidence": {"audit": audit, "arranged": [row["payload"] for row in source.raw_tasks]},
                "origins": origins, "point_work": work}
    return resolve


def test_absent_official_baseline_keeps_original_capture(candidate_case):
    source = _run(candidate_case, "absent")
    original = deepcopy(source.capture)
    data = _read(source)
    assert data["identity"]["state"] == "absent"
    assert data["identity"]["plan_ref"] is None
    assert data["tasks"] == [] and data["source_refs"] == []
    assert data["deferred_operation_ids"] == []
    plan_capture = {"baseline": deepcopy(source.capture["baseline"])}
    assert read_decision_baseline_members(plan_capture, source.facts) == {
        "identity": data["identity"], "operation_refs": []}
    plan_capture["baseline"]["plan_ref"] = "f" * 48
    with pytest.raises(WorkbenchCommandRejected) as exc:
        read_decision_baseline_members(plan_capture, source.facts)
    assert exc.value.code == "candidate_baseline_invalid"
    assert source.capture == original


def test_partial_latest_version_preserves_other_operations_last_official_version(candidate_case):
    case = candidate_case
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    first, original_first = _adopt(case, "first", "B1", "B2")
    # A historical partial formal version predates the full-coverage adopt gate.
    # Current candidate adoption correctly rejects publishing this partial scope.
    case.conn.execute("INSERT INTO Schedule(op_id,machine_id,operator_id,start_time,end_time,lock_status,version) "
                      "SELECT op_id,machine_id,operator_id,start_time,end_time,lock_status,2 FROM Schedule WHERE op_id=?",
                      (case.op_id,))
    case.conn.execute("INSERT INTO ScheduleHistory(version,strategy,batch_count,op_count,result_status,result_summary) "
                      "VALUES(2,'manual',1,1,'success','{}')")
    case.conn.commit()
    second_ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='official' AND version=2").fetchone()[0]
    current = _run(case, "compare", "B1", "B2")
    assert len(current.capture["baseline"]["rows"]) == 1
    before, calls = deepcopy(current.capture), []
    data = _read(current, _resolver({1: original_first}, calls))
    tasks = {row["batch_label"]: row for row in data["tasks"]}
    assert set(tasks) == {"B1", "B2"}
    assert tasks["B1"]["official_version"] == 2
    assert tasks["B1"]["plan_ref"] == second_ref
    assert tasks["B2"]["official_version"] == first["version"]
    assert tasks["B2"]["plan_ref"] == first["plan_ref"]
    assert len({row["task_ref"] for row in tasks.values()}) == 2
    assert data["identity"]["source_candidate_ref"] is None
    assert data["source_refs"][0]["source_candidate_ref"] == original_first.candidate["candidate_ref"]
    assert data["source_refs"][0]["source_run_ref"] == original_first.run["run_ref"]
    assert calls == [(first["plan_ref"], 1), (second_ref, 2)]
    assert {row["version"] for row in data["source_refs"]} == {1, 2}
    assert source_history(data, 1)["result_status"] == "success"
    assert tasks["B2"]["source"] == "internal" and tasks["B1"]["source"] is None
    assert all(row["locked"] is False for row in tasks.values())
    assert read_decision_baseline_members(current.capture, current.facts) == {
        "identity": data["identity"],
        "operation_refs": sorted({row["operation_ref"] for row in data["tasks"]})}
    damaged_capture = deepcopy(current.capture)
    damaged_archive = json.loads(damaged_capture["facts_text"])
    ddl = next(row[3] for row in damaged_archive["schema"] if row[0:2] == ["table", "WorkbenchTaskRefs"])
    columns = ddl_columns(ddl, "WorkbenchTaskRefs", restricted=True)
    retained_task = next(row for row in damaged_archive["tables"]["WorkbenchTaskRefs"]
                         if row[columns.index("ref")] == tasks["B2"]["task_ref"])
    retained_task[columns.index("plan_ref")] = second_ref
    from core.services.workbench.facts.candidate_facts import GenerationFacts
    damaged_capture["facts_text"] = json.dumps(damaged_archive)
    damaged_facts = GenerationFacts(damaged_capture)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        read_decision_baseline_members(current.capture, damaged_facts)
    assert exc.value.code == "candidate_baseline_invalid"
    assert current.capture == before


def source_history(data, version):
    return next(row["history_record"] for row in data["source_refs"] if row["version"] == version)


def test_last_version_selection_keeps_segments_and_excludes_superseded_and_future_rows():
    rows = [{"id": key, "op_id": op, "version": version} for key, op, version in (
        (1, 1, 1), (2, 1, 2), (3, 1, 2), (4, 2, 1), (5, 2, 3))]
    assert [row["id"] for row in _last_official_rows(rows, 2)] == [2, 3, 4]


def test_immutable_zero_point_work_survives_current_operation_edits(candidate_case):
    case = candidate_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0 WHERE id=?", (case.op_id,))
    case.conn.commit()
    official, original = _adopt(case, "point")
    current = _run(case, "point-compare")
    # Changes made after admission cannot replace either saved generation.
    case.conn.execute("UPDATE BatchOperations SET unit_hours=10 WHERE id=?", (case.op_id,))
    case.conn.execute("UPDATE Machines SET name='Changed live lathe' WHERE machine_id='M1'")
    case.conn.execute("UPDATE Schedule SET start_time='2026-09-15 08:00:00',end_time='2026-09-15 08:00:00'")
    case.conn.commit()
    statements = []
    case.conn.set_trace_callback(statements.append)
    case.conn.execute("PRAGMA query_only=ON")
    try:
        data = _read(current, decision_baseline_source_resolver(case.conn))
    finally:
        case.conn.set_trace_callback(None)
        case.conn.execute("PRAGMA query_only=OFF")
    task = data["tasks"][0]
    assert task["plan_ref"] == official["plan_ref"]
    assert task["event_kind"] == "point" and task["duration_seconds"] == 0
    assert task["occupies_resources"] is False
    assert task["machine"]["label"] == "Original lathe"
    assert not any("FROM SCHEDULE " in statement.upper() or "JOIN SCHEDULE " in statement.upper()
                   for statement in statements)
    assert task["start"] == original.tasks[0]["start"]
    missing = _read(current)["tasks"][0]
    assert "event_kind" not in missing
    assert {row["field"] for row in missing["data_gaps"]} >= {"source", "point_evidence"}


def test_adoption_arrangement_and_identity_mismatches_are_reported(candidate_case):
    case = candidate_case
    _official, original = _adopt(case, "drift")
    current = _run(case, "drift-compare")
    base = _resolver({1: original}, [])

    def drift(**kwargs):
        value = base(**kwargs)
        value["evidence"]["arranged"] = deepcopy(value["evidence"]["arranged"])
        value["evidence"]["arranged"][0]["machine_id"] = "M-other"
        return value

    data = _read(current, drift)
    assert read_decision_baseline_members(current.capture, current.facts) == {
        "identity": data["identity"],
        "operation_refs": sorted({row["operation_ref"] for row in data["tasks"]})}
    assert data["identity"]["source_candidate_ref"] == original.candidate["candidate_ref"]
    assert data["identity"]["source_run_ref"] == original.run["run_ref"]
    task = data["tasks"][0]
    assert task["source"] is None
    assert any(row["code"] == "adoption_plan_drift" for row in task["data_gaps"])

    def wrong_identity(**kwargs):
        value = base(**kwargs)
        value["evidence"]["audit"] = {**value["evidence"]["audit"], "version": 2}
        return value

    with pytest.raises(WorkbenchCommandRejected) as exc:
        _read(current, wrong_identity)
    assert exc.value.code == "candidate_baseline_invalid"
    # An admitted directory replacement must not erase the adopted identity or
    # mark that known original ref as missing to the operation-change reader.
    from core.services.workbench.run.decision_impact import _resource_delta
    current.facts.entity_refs[("machine", "M1")] = "e" * 48
    replaced = _read(current, base)["tasks"][0]
    assert replaced["machine"] == original.tasks[0]["machine"]
    assert "machine.admission_identity" in {row["field"] for row in replaced["data_gaps"]}
    assert "machine.ref" not in {row["field"] for row in replaced["data_gaps"]}
    assert _resource_delta(replaced, {"machine": {"ref": "e" * 48}, "data_gaps": []}, "machine") is True
    # A deleted admitted directory initially produces missing-entity/ref gaps;
    # restoring the original resource resolves those gaps at the producer.
    for kind, key, table in (("machine", "M1", "Machines"), ("operator", "O1", "Operators")):
        current.facts.entity_refs.pop((kind, key))
        current.facts.tables[table].pop(key)
    deleted = _read(current, base)["tasks"][0]
    fields = {row["field"] for row in deleted["data_gaps"]}
    for kind in ("machine", "operator"):
        assert deleted[kind] == original.tasks[0][kind]
        assert kind not in fields and kind + ".ref" not in fields
        assert kind + ".admission_identity" in fields
        assert _resource_delta(deleted, {kind: {"ref": "f" * 48}, "data_gaps": []}, kind) is True


def test_formal_deferred_ids_use_original_stage_source_independently_of_current_run(candidate_case):
    case = candidate_case
    second = case.operation(seq=2)
    case.conn.execute("INSERT INTO Materials(material_id,name,unit) VALUES ('STEEL','钢材','件')")
    case.conn.commit()
    operation_ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
                                      (str(second),)).fetchone()[0]
    with TransactionManager(case.conn).transaction():
        WorkbenchBatchMaterialService(case.conn).apply(case.ref("batch", "B1"), {"removed_keys": [], "rows": [{
            "row_key": None, "material_ref": case.ref("material", "STEEL"), "required_quantity": 3,
            "available_quantity": 0, "operation_ref": operation_ref, "arrivals": []}]})
    official, _ = _adopt(case, "stage", _expected_state="partial", material_strategy="stage")
    current = _run(case, "strict-current", ready_check=False, material_strategy="strict")
    assert current.disposition[operation_ref]["status"] == "eligible"
    data = _read(current, decision_baseline_source_resolver(case.conn))
    assert data["deferred_operation_ids"] == [second]
    assert data["source_refs"][0]["deferred_operation_ids"] == [second]
    audit = json.loads(source_history(data, 1)["result_summary"])
    audit.pop("deferred_operation_ids")
    case.conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=?", (json.dumps(audit), official["version"]))
    case.conn.commit()
    legacy = _run(case, "legacy-stage-current", ready_check=False, material_strategy="strict")
    restored = _read(legacy, decision_baseline_source_resolver(case.conn))
    assert restored["deferred_operation_ids"] == [second]
    assert not any(row["field"] == "deferred_operation_ids" for row in restored["source_refs"][0]["data_gaps"])
    missing = _read(legacy)
    assert missing["deferred_operation_ids"] == []
    assert any(row["code"] == "deferred_operation_evidence_missing" for row in missing["source_refs"][0]["data_gaps"])
    audit["deferred_operation_ids"] = [case.op_id]
    case.conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=?", (json.dumps(audit), official["version"]))
    case.conn.commit()
    wrong = _run(case, "invalid-stage-current", ready_check=False, material_strategy="strict")
    invalid = _read(wrong, decision_baseline_source_resolver(case.conn))
    assert invalid["deferred_operation_ids"] == []
    assert any(row["code"] == "deferred_operation_evidence_invalid" for row in invalid["source_refs"][0]["data_gaps"])


def test_source_runtime_effort_and_type_keep_saved_context_without_recalculation():
    op_ref, type_ref, runtime_type_ref = "1" * 48, "2" * 48, "3" * 48
    ledger = {"effort_basis": "runtime_requirement_v1", "items": [
        {"op_id": 7, "operation_ref": op_ref, "setup_standard_hours": 1.5,
         "processing_standard_hours": 6.0, "required_standard_hours": 7.5}]}
    operation = {"id": 7, "source": "internal", "op_type_id": "TURN", "op_type_name": "精车",
                 "setup_hours": 100, "unit_hours": 200}
    archive = {"schema": [["table", "OpTypes", "OpTypes", "CREATE TABLE OpTypes(op_type_id TEXT, name TEXT)"]],
               "tables": {"OpTypes": [["TURN", "车削工种"], ["MILL", "铣削工种"]]}}
    facts = SimpleNamespace(operations={op_ref: 7}, tables={"BatchOperations": {7: operation}},
                            entity_refs={("op_type", "TURN"): type_ref, ("op_type", "MILL"): runtime_type_ref},
                            archive=archive, table=lambda name: _table(archive, name), execution={op_ref: {"target_quantity": 5, "remaining_quantity": 2}})
    candidate = SimpleNamespace(receipt={"operation_effort": ledger}, facts=facts,
                                candidate={"artifact": {"results": [{"op_id": 7, "op_type_id": "MILL", "op_type_name": "精车"}]}})
    effort, types, standards = _operation_metadata(candidate, {"basis": "candidate_adoption"})
    assert effort is ledger
    assert types == {op_ref: {"ref": runtime_type_ref, "label": "铣削工种"}}
    assert standards == {op_ref: {"operation": {"source": "internal", "setup_hours": 100, "unit_hours": 200},
                                 "execution": {"target_quantity": 5, "remaining_quantity": 2}}}
    candidate.receipt = {}
    candidate.candidate["artifact"]["results"][0].pop("op_type_id")
    old_effort, old_types, _ = _operation_metadata(candidate, {"basis": "candidate_adoption"})
    assert old_effort is None
    assert old_types == {op_ref: {"ref": type_ref, "label": "车削工种"}}
    head = {"admission": {"source": {"operation_effort": ledger, "operation_types": types,
                                      "trial_operation_types": old_types}, "facts": {"tables": {
        "WorkbenchEntityRefs": [{"kind": "op_type", "entity_key": "MILL", "ref": runtime_type_ref, "active": 1},
                                {"kind": "op_type", "entity_key": "TURN", "ref": type_ref, "active": 1}],
        "OpTypes": [{"op_type_id": "MILL", "name": "铣削工种"}, {"op_type_id": "TURN", "name": "车削工种"}]}}}}
    rows = [{"operation_ref": op_ref, "original": {"operation": operation, "execution": facts.execution[op_ref]}}]
    # A base requirement cannot supply a missing saved trial's current ledger.
    assert _operation_metadata(({}, head, rows), {"basis": "trial_adoption"}) == (None, types, standards)
    saved = {"operation_effort": ledger}
    assert _operation_metadata((saved, head, rows), {"basis": "trial_adoption"})[0] is ledger
    rows[0]["current"] = {"operation_effort": ledger["items"][0]}
    assert _operation_metadata((saved, head, rows), {"basis": "trial_adoption"})[1] == old_types
    rows[0]["current"] = {}
    assert _operation_metadata((saved, head, rows), {"basis": "trial_adoption"})[1] == types
    head["admission"]["source"].pop("operation_types")
    assert _operation_metadata(({}, head, rows), {"basis": "trial_adoption"})[1] == {op_ref: {"ref": None, "label": None}}


@pytest.mark.parametrize("captured", [False, True])
def test_trial_resolver_prepares_each_scenario_once_and_keeps_original_resource_context(monkeypatch, captured):
    import sqlite3

    from core.services.workbench.facts import adoption_baseline_sources as sources

    scenario_ref, draft_ref, baseline_ref = "1" * 48, "2" * 48, "3" * 48
    operation_ref, supplier_ref, machine_ref, operator_ref = (str(index) * 48 for index in range(4, 8))

    def archive(label):
        return {"tables": {
            "Machines": [{"machine_id": "M", "name": label + " machine"}],
            "Operators": [{"operator_id": "O", "name": label + " operator"}],
            "Suppliers": [{"supplier_id": "S", "name": label + " supplier"}],
            "OpTypes": [], "WorkbenchEntityRefs": [
                {"kind": kind, "entity_key": key, "ref": ref, "active": 1}
                for kind, key, ref in (("supplier", "S", supplier_ref), ("machine", "M", machine_ref),
                                      ("operator", "O", operator_ref))]}}

    original = sources._TrialResourceFacts(archive("original"))
    saved = {"scenario_ref": scenario_ref, "baseline": {"plan_ref": baseline_ref, "version": 1}}
    source = {"deferred_operation_ids": [], "deferred_operation_issues": []}
    if captured:
        source["capture"] = {"original": True}
    head = {"draft_ref": draft_ref, "scenario_revision": 2,
            "admission": {"source": source, "facts": archive("assigned")}}
    rows = [{"operation_ref": operation_ref,
             "original": {"operation": {"id": 9, "source": "external", "supplier_id": "S"}, "execution": {}},
             "current": {"machine_id": "M", "operator_id": "O",
                         "start": "2026-09-09T08:00:00", "end": "2026-09-09T09:00:00"}}]
    calls = {"scenario": 0, "generation": 0, "assigned": 0}
    resource_facts = sources._TrialResourceFacts

    def load(conn, ref):
        assert ref == scenario_ref
        calls["scenario"] += 1
        return saved, head, rows

    def generation(capture):
        assert capture is source["capture"]
        calls["generation"] += 1
        return original

    def assigned(facts):
        assert facts is head["admission"]["facts"]
        calls["assigned"] += 1
        return resource_facts(facts)

    monkeypatch.setattr(sources, "load_saved_scenario", load)
    monkeypatch.setattr(sources, "GenerationFacts", generation)
    monkeypatch.setattr(sources, "_TrialResourceFacts", assigned)
    with sqlite3.connect(":memory:") as conn:
        resolve = decision_baseline_source_resolver(conn)
        for version in (2, 3):
            audit = {"source": "workbench_trial_adoption", "scenario_ref": scenario_ref, "draft_ref": draft_ref,
                     "baseline_ref": baseline_ref, "baseline_version": 1, "version": version,
                     "proof": {"proof_version": "content_refs_v1", "scenario_ref": scenario_ref,
                               "draft_ref": draft_ref, "scenario_revision": 2,
                               "baseline_ref": baseline_ref, "baseline_version": 1}}
            from core.models.workbench_command import canonical_json

            value = resolve(plan_ref="8" * 48, version=version,
                            history={"version": version, "result_summary": canonical_json(audit)})
            prepared = value["evidence"]["trial_source"]
            assert (prepared.resources is prepared.assigned_resources) is (not captured)
            assert value["origins"][9]["supplier"]["label"] == ("original" if captured else "assigned") + " supplier"
            assert value["origins"][9]["machine"]["label"] == "assigned machine"
            assert value["point_work"]() == {}
            assert sources.read_adoption_operation_facts(conn, value["evidence"]) == value["origins"]
    assert calls == {"scenario": 1, "generation": int(captured), "assigned": 1}

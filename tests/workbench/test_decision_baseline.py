"""Decision baselines use captured last-per-operation arrangements and identities."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.scheduler_history_parser import parse_result_summary_payload
from core.models.workbench_batch_material import normalize_material_changes
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch.facts import BatchFacts
from core.services.workbench.batch.materials import WorkbenchBatchMaterialService
from core.services.workbench.batch.scope import BatchFactScope
from core.services.workbench.facts.adoption_baseline_sources import prepare_trial_adoption_facts
from core.services.workbench.facts.candidate_facts import archived_table
from core.services.workbench.facts.candidate_read_source import read_candidate_source
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.decision_baseline import (
    _last_official_rows,
    read_decision_baseline,
)
from core.services.workbench.facts.decision_baseline_source import (
    _candidate_operation_metadata,
    _trial_operation_metadata,
    decision_baseline_source_resolver,
)
from core.services.workbench.facts.trial_scenario_archive import SavedTrialScenario
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
    return read_decision_baseline(source.capture, source.facts, source.disposition,
                                  source_resolver=resolver or _resolver({}, []))


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
                "origins": origins, "point_work": lambda: work,
                "operation_effort": None, "operation_types": {}, "operation_standards": {}}
    return resolve


def test_absent_official_baseline_keeps_original_capture(candidate_case):
    source = _run(candidate_case, "absent")
    original = deepcopy(source.capture)
    data = _read(source)
    assert data["identity"]["state"] == "absent"
    assert data["identity"]["plan_ref"] is None
    assert data["tasks"] == [] and data["source_refs"] == []
    assert data["deferred_operation_ids"] == []
    assert source.capture == original


def test_latest_adopted_version_keeps_saved_identities_and_rejects_damaged_bindings(candidate_case):
    case = candidate_case
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    first, _original_first = _adopt(case, "first", "B1", "B2")
    # 每次采用都覆盖已有正式安排的完整工序范围，所以全部工序的最后正式安排都在第二版。
    second, original_second = _adopt(case, "second", "B1", "B2")
    assert second["version"] == first["version"] + 1
    current = _run(case, "compare", "B1", "B2")
    assert len(current.capture["baseline"]["rows"]) == 2
    before, calls = deepcopy(current.capture), []
    data = _read(current, _resolver({second["version"]: original_second}, calls))
    tasks = {row["batch_label"]: row for row in data["tasks"]}
    assert set(tasks) == {"B1", "B2"}
    assert {row["official_version"] for row in tasks.values()} == {second["version"]}
    assert {row["plan_ref"] for row in tasks.values()} == {second["plan_ref"]}
    assert len({row["task_ref"] for row in tasks.values()}) == 2
    assert data["identity"]["source_candidate_ref"] == original_second.candidate["candidate_ref"]
    assert data["identity"]["source_run_ref"] == original_second.run["run_ref"]
    assert calls == [(second["plan_ref"], second["version"])]
    assert [row["version"] for row in data["source_refs"]] == [second["version"]]
    assert source_history(data, second["version"])["result_status"] == "success"
    assert {row["source"] for row in tasks.values()} == {"internal"}
    assert all(row["locked"] is False for row in tasks.values())
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
        assert value["evidence"] is not None
        value["evidence"]["arranged"] = deepcopy(value["evidence"]["arranged"])
        value["evidence"]["arranged"][0]["machine_id"] = "M-other"
        return value

    data = _read(current, drift)
    assert data["identity"]["source_candidate_ref"] == original.candidate["candidate_ref"]
    assert data["identity"]["source_run_ref"] == original.run["run_ref"]
    task = data["tasks"][0]
    assert task["source"] is None
    assert any(row["code"] == "adoption_plan_drift" for row in task["data_gaps"])

    def wrong_identity(**kwargs):
        value = base(**kwargs)
        assert value["evidence"] is not None
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
        batch_ref = case.ref("batch", "B1")
        scope = BatchFactScope(BatchFacts(case.conn), command=True, mode="single_instance", target_ref=batch_ref)
        WorkbenchBatchMaterialService(case.conn).apply_normalized(scope, batch_ref, normalize_material_changes({"removed_keys": [], "rows": [{
            "row_key": None, "material_ref": case.ref("material", "STEEL"), "required_quantity": 3,
            "available_quantity": 0, "operation_ref": operation_ref, "arrivals": []}]}))
    _adopt(case, "stage", _expected_state="partial", material_strategy="stage")
    current = _run(case, "strict-current", ready_check=False, material_strategy="strict")
    assert current.disposition[operation_ref]["status"] == "eligible"
    data = _read(current, decision_baseline_source_resolver(case.conn))
    assert data["deferred_operation_ids"] == [second]
    assert data["source_refs"][0]["deferred_operation_ids"] == [second]


def test_source_runtime_effort_and_type_keep_saved_context_without_recalculation():
    op_ref, unrelated_ref, type_ref, runtime_type_ref = "1" * 48, "9" * 48, "2" * 48, "3" * 48
    ledger = {"effort_basis": "runtime_requirement_v1", "items": [
        {"op_id": 7, "operation_ref": op_ref, "setup_standard_hours": 1.5,
         "processing_standard_hours": 6.0, "required_standard_hours": 7.5}]}
    operation = {"id": 7, "source": "internal", "op_type_id": "TURN", "op_type_name": "精车",
                 "setup_hours": 100, "unit_hours": 200}
    unrelated = {"id": 8, "source": "internal", "op_type_id": "TURN", "op_type_name": "无关",
                 "setup_hours": 10, "unit_hours": 20}
    archive = {"schema": [["table", "OpTypes", "OpTypes", "CREATE TABLE OpTypes(op_type_id TEXT, name TEXT)"]],
               "columns": {"OpTypes": ["op_type_id", "name"]},
               "tables": {"OpTypes": [["TURN", "车削工种"], ["MILL", "铣削工种"]]}}
    facts = SimpleNamespace(
        operations={op_ref: 7, unrelated_ref: 8},
        tables={"BatchOperations": {7: operation, 8: unrelated}},
        entity_refs={("op_type", "TURN"): type_ref, ("op_type", "MILL"): runtime_type_ref},
        archive=archive,
        table=lambda name: archived_table(archive, name),
        execution={op_ref: {"target_quantity": 5, "remaining_quantity": 2},
                   unrelated_ref: {"target_quantity": 9, "remaining_quantity": 9}},
    )
    candidate = SimpleNamespace(
        receipt={"operation_effort": ledger},
        facts=facts,
        raw_tasks=[{"operation_ref": op_ref, "payload": {"op_id": 7}}],
        candidate={"artifact": {"results": [{"op_id": 7, "op_type_id": "MILL", "op_type_name": "精车"}]}},
    )
    effort, types, standards = _candidate_operation_metadata(candidate)
    assert effort is ledger
    assert types == {op_ref: {"ref": runtime_type_ref, "label": "铣削工种"}}
    assert standards == {op_ref: {"operation": {"source": "internal", "setup_hours": 100, "unit_hours": 200},
                                  "execution": {"target_quantity": 5, "remaining_quantity": 2}}}
    candidate.candidate["artifact"]["results"][0]["op_type_id"] = None
    _, unknown_types, _ = _candidate_operation_metadata(candidate)
    assert unknown_types == {op_ref: {"ref": None, "label": None}}
    slot_types = {op_ref: {"ref": type_ref, "label": "车削工种"}}
    head = {"admission": {"source": {"operation_effort": ledger, "operation_types": types,
                                      "trial_operation_types": slot_types}, "facts": {"tables": {
        "WorkbenchEntityRefs": [{"kind": "op_type", "entity_key": "MILL", "ref": runtime_type_ref, "active": 1},
                                {"kind": "op_type", "entity_key": "TURN", "ref": type_ref, "active": 1}],
        "OpTypes": [{"op_type_id": "MILL", "name": "铣削工种"}, {"op_type_id": "TURN", "name": "车削工种"}]}}}}
    rows = [{"operation_ref": op_ref, "original": {"operation": operation, "execution": facts.execution[op_ref]}}]

    def trial_prepared(saved_payload):
        return prepare_trial_adoption_facts(SavedTrialScenario(saved_payload, head, rows))

    # A base requirement cannot supply a missing saved trial's current ledger.
    assert _trial_operation_metadata(trial_prepared({"operation_effort": None})) == (
        None, types, standards)
    saved = {"operation_effort": ledger}
    assert _trial_operation_metadata(trial_prepared(saved))[0] is ledger
    rows[0]["current"] = {"operation_effort": ledger["items"][0]}
    assert _trial_operation_metadata(trial_prepared(saved))[1] == slot_types
    rows[0]["current"] = {}
    assert _trial_operation_metadata(trial_prepared(saved))[1] == types
    # 正式计划来源认不出原工种时，生产者逐工序写下明确未知，不另造 None 整表。
    head["admission"]["source"]["operation_types"] = {op_ref: {"ref": None, "label": None}}
    assert _trial_operation_metadata(trial_prepared({"operation_effort": None}))[1] == {
        op_ref: {"ref": None, "label": None}}


@pytest.mark.parametrize("captured", [False, True])
def test_trial_resolver_prepares_each_scenario_once_and_keeps_original_resource_context(monkeypatch, captured):
    import sqlite3

    from core.infrastructure.read_evidence import read_evidence_scope
    from core.services.workbench.facts import adoption_baseline_sources as sources
    from core.services.workbench.facts import decision_baseline_source as baseline_source

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
    saved = {"scenario_ref": scenario_ref, "baseline": {"plan_ref": baseline_ref, "version": 1},
             "operation_effort": None}
    # 以候选为基础的试调来源保存 capture 与全部处置；以正式计划为基础的保存待料编号与缺口。
    source = (
        {"capture": {"original": True, "input": {}}, "dispositions": {},
         "operation_types": {}, "trial_operation_types": {}}
        if captured
        else {"deferred_operation_ids": [], "deferred_operation_issues": [],
              "operation_types": {}, "trial_operation_types": {}}
    )
    head = {"draft_ref": draft_ref, "scenario_revision": 2,
            "admission": {"source": source, "facts": archive("assigned")}}
    rows = [{"operation_ref": operation_ref,
             "original": {"operation": {"id": 9, "source": "external", "supplier_id": "S"}, "execution": {}},
             "current": {"machine_id": "M", "operator_id": "O",
                         "start": "2026-09-09T08:00:00", "end": "2026-09-09T09:00:00"}}]
    calls = {"scenario": 0, "generation": 0, "assigned": 0, "metadata": 0, "origins": 0}
    resource_facts = sources._TrialResourceFacts
    real_metadata = baseline_source._trial_operation_metadata
    real_origins = sources._adoption_operation_facts

    def load(conn, ref):
        assert ref == scenario_ref
        calls["scenario"] += 1
        return SavedTrialScenario(saved, head, rows)

    def generation(capture):
        assert capture is source["capture"]
        calls["generation"] += 1
        return original

    def assigned(facts):
        assert facts is head["admission"]["facts"]
        calls["assigned"] += 1
        return resource_facts(facts)

    def count_metadata(prepared):
        calls["metadata"] += 1
        return real_metadata(prepared)

    def count_origins(evidence):
        calls["origins"] += 1
        return real_origins(evidence)

    monkeypatch.setattr(sources, "load_saved_scenario", load)
    monkeypatch.setattr(sources, "cached_generation_facts", generation)
    monkeypatch.setattr(sources, "_TrialResourceFacts", assigned)
    monkeypatch.setattr(baseline_source, "_trial_operation_metadata", count_metadata)
    monkeypatch.setattr(sources, "_adoption_operation_facts", count_origins)
    monkeypatch.setattr(
        "core.services.workbench.facts.decision_baseline_source.read_adoption_record",
        lambda conn, *, plan_ref, version, history: ("trial_adoption", json.loads(history["result_summary"]), {}),
    )
    with sqlite3.connect(":memory:") as conn:
        conn.execute("BEGIN")
        with read_evidence_scope(conn):
            resolve = decision_baseline_source_resolver(conn)
            for version in (2, 3):
                audit = {"source": "workbench_trial_adoption", "scenario_ref": scenario_ref, "draft_ref": draft_ref,
                         "baseline_ref": baseline_ref, "baseline_version": 1, "version": version,
                         "proof": {"proof_version": "content_refs_v1", "scenario_ref": scenario_ref,
                                   "draft_ref": draft_ref, "scenario_revision": 2,
                                   "baseline_ref": baseline_ref, "baseline_version": 1}}
                from core.shared.strict_json import canonical_json

                value = resolve(plan_ref="8" * 48, version=version,
                                history={"version": version, "result_summary": canonical_json(audit)})
                prepared = value["evidence"]["trial_source"]
                assert (prepared.resources is prepared.assigned_resources) is (not captured)
                assert value["origins"][9]["supplier"]["label"] == ("original" if captured else "assigned") + " supplier"
                assert value["origins"][9]["machine"]["label"] == "assigned machine"
                assert value["point_work"]() == {}
                assert sources.read_adoption_operation_facts(conn, value["evidence"]) == value["origins"]
    assert calls == {"scenario": 1, "generation": int(captured), "assigned": 1, "metadata": 1, "origins": 1}


def test_candidate_metadata_scopes_to_arranged_members_and_prepares_once_across_consumers(candidate_case, monkeypatch):
    from unittest.mock import Mock

    from core.infrastructure.connection_guards import query_only
    from core.infrastructure.read_evidence import read_evidence_scope
    from core.services.workbench.facts import adoption_baseline_sources as sources
    from core.services.workbench.facts import decision_baseline_source as baseline_source
    from core.shared.strict_json import canonical_json
    from tests.workbench.execution_ledger_support import publish_official_plan

    case = candidate_case
    case.batch("B2")
    op_b = case.operation("B2")
    case.batch("B3")
    op_c = case.operation("B3")
    case.conn.commit()

    def op_ref_for(op_id):
        return case.conn.execute(
            "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
            (str(op_id),),
        ).fetchone()[0]

    ref_a, ref_b, ref_c = op_ref_for(case.op_id), op_ref_for(op_b), op_ref_for(op_c)

    # 1. 来源安排 A/B、库内存在无关 C：只为 A/B 生成元数据；B1 作为排产窗口外受保护 seed 时同样完整包含 A/B 且排除无关 C。
    official_v1, source_ab = _adopt(case, "ab-only", "B1", "B2")
    assert set(source_ab.facts.operations) == {ref_a, ref_b, ref_c}
    _, types_ab, standards_ab = _candidate_operation_metadata(source_ab)
    assert set(types_ab) == set(standards_ab) == {ref_a, ref_b}

    full_compare = _run(case, "full-v1", "B1", "B2")

    case.command(
        "create",
        case.task(official_v1["version"], case.op_id),
        case.values(3, actual_end="2026-09-09T08:45:00", effective_processing_hours=0.75),
    )
    seeded_out_of_window = _run(
        case, "seed-a-out-of-window", "B1", "B2", start_date="2026-09-10", completed_policy="preserve_actuals"
    )
    assert {row["payload"]["op_id"] for row in seeded_out_of_window.raw_tasks} == {case.op_id, op_b}
    _, seeded_types, seeded_standards = _candidate_operation_metadata(seeded_out_of_window)
    assert set(seeded_types) == set(seeded_standards) == {ref_a, ref_b}

    # 2. v2 仅重排 B2（不记录原候选），使 A 的最后正式安排仍在 v1：先读 subset（仅消费 A）再读 full（消费 A+B），并跨版本复用。
    publish_official_plan(
        case.conn,
        2,
        [{"op_id": op_b, "machine_id": "M1", "operator_id": "O1",
          "start_time": "2026-09-09T10:00:00", "end_time": "2026-09-09T10:45:00"}],
        record_source=False,
    )
    case.conn.commit()
    subset_compare = _run(case, "subset-v2", "B1", "B2", completed_policy="preserve_actuals")

    meta_spy = Mock(wraps=baseline_source._candidate_operation_metadata)
    origins_spy = Mock(wraps=sources._adoption_operation_facts)
    monkeypatch.setattr(baseline_source, "_candidate_operation_metadata", meta_spy)
    monkeypatch.setattr(sources, "_adoption_operation_facts", origins_spy)

    v1_summary = case.conn.execute(
        "SELECT result_summary FROM ScheduleHistory WHERE version=?", (official_v1["version"],)
    ).fetchone()[0]
    v3_audit = {**json.loads(v1_summary), "version": 3}

    with TransactionManager(case.conn).transaction(), query_only(case.conn), read_evidence_scope(case.conn):
        resolver = decision_baseline_source_resolver(case.conn)
        subset_baseline = read_decision_baseline(
            subset_compare.capture, subset_compare.facts, subset_compare.disposition, source_resolver=resolver
        )
        assert set(subset_baseline["operation_types"]) == {ref_a}
        assert meta_spy.call_count == 1
        assert origins_spy.call_count == 1

        full_baseline = read_decision_baseline(
            full_compare.capture, full_compare.facts, full_compare.disposition, source_resolver=resolver
        )
        assert set(full_baseline["operation_types"]) == {ref_a, ref_b}
        assert set(full_baseline["operation_standards"]) == {ref_a, ref_b}
        assert set(full_baseline["operation_efforts"]) == {ref_a, ref_b}
        assert meta_spy.call_count == 1
        assert origins_spy.call_count == 1

        with monkeypatch.context() as cross_ver:
            cross_ver.setattr(
                baseline_source,
                "read_adoption_record",
                lambda conn, *, plan_ref, version, history: (
                    "candidate_adoption", json.loads(history["result_summary"]), {}
                ),
            )
            resolved_v3 = resolver(
                plan_ref="8" * 48,
                version=3,
                history={"version": 3, "result_summary": canonical_json(v3_audit), "result_status": "success"},
            )
            assert set(resolved_v3["operation_types"]) == {ref_a, ref_b}
            assert meta_spy.call_count == 1
            assert origins_spy.call_count == 1


def test_large_archived_sequences_sort_numerically_across_workspace_baseline_reference_and_completion(
    candidate_case, monkeypatch
):
    from core.models.workbench_run_candidate import RunCandidateReadScope
    from core.services.workbench.facts.completion_scope import project_completion_summary
    from core.services.workbench.run.candidate_baseline import WorkbenchRunCandidateBaselineQueryService
    from core.services.workbench.run.candidates import WorkbenchRunCandidateQueryService
    from core.services.workbench.run.decision_session import decision_read
    from core.services.workbench.run.decision_workspace import read_reference_workspace
    from data.repositories.workbench_run_candidate_repo import WorkbenchRunCandidateRepository

    case = candidate_case
    _adopt(case, "seq-official", "B1")

    op_2 = case.operation("B1", seq=2, unit_hours=1)
    op_3 = case.operation("B1", seq=3, unit_hours=1)
    op_4 = case.operation("B1", seq=4, unit_hours=1)
    op_5 = case.operation("B1", seq=5, unit_hours=1)
    op_6 = case.operation("B1", seq=6, unit_hours=1)
    material_rows = []
    for idx, deferred_op in enumerate((op_3, op_4, op_5, op_6), start=3):
        mat_code = f"MAT_{idx}"
        case.conn.execute("INSERT INTO Materials(material_id,name,unit) VALUES (?,?,'件')", (mat_code, mat_code))
        op_ref = case.conn.execute(
            "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
            (str(deferred_op),),
        ).fetchone()[0]
        material_rows.append(
            {
                "row_key": None,
                "material_ref": case.ref("material", mat_code),
                "required_quantity": 2,
                "available_quantity": 0,
                "operation_ref": op_ref,
                "arrivals": [],
            }
        )
    case.conn.commit()
    with TransactionManager(case.conn).transaction():
        batch_ref = case.ref("batch", "B1")
        scope = BatchFactScope(BatchFacts(case.conn), command=True, mode="single_instance", target_ref=batch_ref)
        WorkbenchBatchMaterialService(case.conn).apply_normalized(
            scope,
            batch_ref,
            normalize_material_changes({"removed_keys": [], "rows": material_rows}),
        )

    current = _run(case, "seq-stage", "B1", _expected_state="partial", material_strategy="stage")
    run_ref = current.run["run_ref"]
    cand_ref = current.candidate["candidate_ref"]

    seq_overrides = {
        case.op_id: 10,
        op_2: (1 << 53) + 5,
        op_3: 10_000_000_000_000_000,
        op_4: 1 << 53,
        op_5: 2,
        op_6: None,
    }
    original_capture = WorkbenchRunCandidateRepository.job_capture

    def capture_with_large_sequences(repo_self, target_run_ref):
        row = original_capture(repo_self, target_run_ref)
        if row is None or target_run_ref != run_ref:
            return row
        facts = json.loads(row[3])
        cols = facts["columns"]["BatchOperations"]
        id_idx, seq_idx = cols.index("id"), cols.index("seq")
        for op_row in facts["tables"]["BatchOperations"]:
            if isinstance(op_row, list) and op_row[id_idx] in seq_overrides:
                op_row[seq_idx] = seq_overrides[op_row[id_idx]]
            elif isinstance(op_row, dict) and op_row["id"] in seq_overrides:
                op_row["seq"] = seq_overrides[op_row["id"]]
        patched_text = json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
        return (*row[:3], patched_text, *row[4:7], len(patched_text.encode("utf-8")))

    monkeypatch.setattr(WorkbenchRunCandidateRepository, "job_capture", capture_with_large_sequences)
    noop_bind = lambda scope, state: state  # noqa: E731

    ws_asc, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(
        RunCandidateReadScope(cand_ref, sort="sequence", order="asc"), bind_snapshot=noop_bind
    )
    ws_desc, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(
        RunCandidateReadScope(cand_ref, sort="sequence", order="desc"), bind_snapshot=noop_bind
    )
    assert [row["sequence"] for row in ws_asc["tasks"]] == [10, str((1 << 53) + 5)]
    assert [row["sequence"] for row in ws_desc["tasks"]] == [str((1 << 53) + 5), 10]
    expected_unplanned_asc = [2, str(1 << 53), "10000000000000000", None]
    assert [row["sequence"] for row in ws_asc["unplanned_operations"]] == expected_unplanned_asc
    assert [row["sequence"] for row in ws_desc["unplanned_operations"]] == list(reversed(expected_unplanned_asc))

    base_asc, _ = WorkbenchRunCandidateBaselineQueryService(case.conn).baseline(
        RunCandidateReadScope(cand_ref, sort="sequence", order="asc"), bind_snapshot=noop_bind
    )
    base_desc, _ = WorkbenchRunCandidateBaselineQueryService(case.conn).baseline(
        RunCandidateReadScope(cand_ref, sort="sequence", order="desc"), bind_snapshot=noop_bind
    )
    expected_all_asc = [2, 10, str(1 << 53), str((1 << 53) + 5), "10000000000000000", None]
    assert [row["sequence"] for row in base_asc["comparisons"]] == expected_all_asc
    assert [row["sequence"] for row in base_desc["comparisons"]] == list(reversed(expected_all_asc))

    ref_ws, _ = read_reference_workspace(
        case.conn, run_ref, bind_snapshot=noop_bind, selected_candidate_ref=cand_ref, comparison_mode="admission_official"
    )
    assert [row["sequence"] for row in ref_ws["unplanned_operations"]] == [
        2,
        str(1 << 53),
        str((1 << 53) + 5),
        "10000000000000000",
        None,
    ]

    with decision_read(case.conn, run_ref, selected_candidate_ref=cand_ref) as source:
        detailed_scope = source.completion.scope(cand_ref, details=True)
        recomputed_scope = project_completion_summary(
            source.completion.delivery(cand_ref), source.completion.work_items(cand_ref)
        )
    assert [row["sequence"] for row in detailed_scope["remaining_batches"][0]["operations"]] == expected_unplanned_asc
    assert recomputed_scope["deferred_operation_refs"] == detailed_scope["deferred_operation_refs"]

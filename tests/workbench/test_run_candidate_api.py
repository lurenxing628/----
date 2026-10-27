"""Real full Flask app integration plus terminal catalog and snapshot boundaries."""

import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

import pytest
from flask import Blueprint

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_analysis import operation_metrics
from core.models.workbench_run_baseline import RunCandidateBaselineScope, _resource_change
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.facts.candidate_archive import load_adoption_candidate
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.candidate_projection import algorithm_facts
from core.services.workbench.facts.candidate_read_source import read_candidate_source
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_tasks import filter_workspace, task_resource
from core.services.workbench.run.candidate_analysis import read_candidate_analysis
from core.services.workbench.run.candidate_baseline import WorkbenchRunCandidateBaselineQueryService
from core.services.workbench.run.candidates import WorkbenchRunCandidateQueryService
from core.services.workbench.run.decision_queries import read_decision_details
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests._support.excel_templates import point_env_at_shared
from tests.workbench.run_candidate_adoption_support import INTENT, service
from tests.workbench.run_candidate_support import BASE, compute, corrupt_update, read, state
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.trial_adoption_support import saved_scenario
from tests.workbench.trial_adoption_support import service as trial_adopter
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401
from web.routes.workbench.run_candidates import register_run_candidate_routes


def test_full_app_explicit_registration_only_temporary_connections(candidate_case, tmp_path, monkeypatch):
    case = candidate_case
    run_ref, refs = compute(case)
    for key, path in (("APS_DB_PATH", case.path), ("APS_LOG_DIR", tmp_path / "logs"), ("APS_BACKUP_DIR", tmp_path / "backups")):
        monkeypatch.setenv(key, str(path))
    monkeypatch.setenv("APS_ENV", "development")
    point_env_at_shared(monkeypatch)
    original = sqlite3.connect
    connections = []

    def guarded(path, *args, **kwargs):
        value = url2pathname(urlsplit(str(path)).path) if str(path).startswith("file:") else str(path)
        assert value == ":memory:" or Path(value).resolve() == case.path.resolve(), "Unexpected nonfixture SQLite path"
        connections.append(value)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded)
    from web.bootstrap.entrypoint import create_app_with_mode
    app = create_app_with_mode("default")
    bp = Blueprint("bl_full_app_candidates", __name__)
    register_run_candidate_routes(bp)
    app.register_blueprint(bp)
    client = app.test_client()
    before = state(case.conn)
    catalog = read(client, "/runs/" + run_ref + "/candidates")
    assert catalog["data"]["candidate_count"] == len(refs)
    result = read(client, "/candidates/" + refs[0])
    generation = result["data"]["generation"]
    assert generation["baseline"] == {"baseline_ref": None, "version": None, "kind": "admission_official",
                                      "captured_at": generation["accepted_at"], "captured_task_count": 0}
    artifact = json.loads(case.conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=?", (refs[0],)).fetchone()[0])
    if artifact.get("generation_policy_version") == "unified_search_v1":
        assert 1 <= len(refs) <= 3
        assert generation["algorithm"] == algorithm_facts(artifact)
        assert generation["algorithm"]["target_objectives"] == artifact["target_objectives"]
        assert list(artifact["evaluations"]) != artifact["target_objectives"]
    else:
        assert len(refs) == 4
        assert generation["algorithm"] == {"mode": "greedy", "mode_label": "快速计算",
                                           "strategy": "priority_first", "strategy_label": "优先级优先"}
    token = result["meta"]["snapshot_ref"]
    from web.routes.workbench import run_candidates

    with monkeypatch.context() as patch:
        patch.setattr(run_candidates, "_response", lambda *_: pytest.fail("Downloads must not rehearse a discarded JSON envelope"))
        for fmt in ("csv", "xlsx"):
            response = client.get(BASE + "/candidates/" + refs[0] + "/export", query_string={"format": fmt, "snapshot_ref": token})
            assert response.status_code == 200 and response.headers["X-Workbench-Task-Count"] == "1"
            if fmt == "csv":
                csv_size = len(response.data)
        patch.setattr(run_candidates, "MAX_RESPONSE_BYTES", csv_size - 1)
        oversized = client.get(BASE + "/candidates/" + refs[0] + "/export", query_string={"format": "csv", "snapshot_ref": token})
        assert oversized.status_code == 413 and oversized.get_json()["error"]["code"] == "candidate_capacity_exceeded"
    assert state(case.conn) == before
    assert connections and str(case.path) in connections
    assert client.post(BASE + "/candidates/" + refs[0]).status_code == 405


def test_known_time_change_is_counted_while_resource_and_supplier_gaps_remain_explained():
    row = {"operation_ref": "op", "batch_ref": "batch", "selected_at_admission": True,
           "status": "matched", "comparison_available": True, "candidate": {"source": "external"},
           "baseline_segments": [{"source": "external", "data_gaps": []}],
           "delta": {"start_hours": 2, "end_hours": 2, "machine_changed": None, "operator_changed": None,
                     "supplier_changed": None}}
    baseline = {"comparisons": [row], "rows_complete": True, "operation_count": 1, "full_operation_count": 1}
    metrics, operations = operation_metrics(baseline, ["batch"])
    assert metrics["changed_operation_count"]["value"] == 1
    assert operations["unknown_operation_refs"] == [] and operations["machine_unknown_operation_refs"] == ["op"]
    assert {reason["code"] for reason in operations["issues"][0]["reasons"]} == {
        "resource_identity_unavailable", "historical_supplier_not_recorded"}
    row["delta"].update(start_hours=0, end_hours=0)
    metrics, operations = operation_metrics(baseline, ["batch"])
    assert metrics["changed_operation_count"]["value"] is None
    assert operations["unknown_operation_refs"] == ["op"]
    row["candidate"]["source"] = "internal"
    row["baseline_segments"][0]["source"] = None
    row["delta"].update(machine_changed=False, operator_changed=False)
    metrics, operations = operation_metrics(baseline, ["batch"])
    assert metrics["changed_operation_count"]["value"] is None
    assert {reason["code"] for reason in operations["issues"][0]["reasons"]} == {"historical_source_unavailable"}
    row["delta"]["start_hours"] = 1
    metrics, _ = operation_metrics(baseline, ["batch"])
    assert metrics["changed_operation_count"]["value"] == 1


@pytest.mark.parametrize("adoption_source", ["candidate", "trial_candidate", "trial_plan"])
def test_adopted_external_supplier_uses_original_lineage_and_null_resources_are_known(trial_case, adoption_source):
    case = trial_case
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('XT','Heat treatment','external')")
    case.conn.executemany("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days) VALUES (?,?,'XT',2)",
                         (("XS1", "Original supplier"), ("XS2", "Second supplier")))
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                      "VALUES ('P1',2,'XT','Heat treatment','external','XS1',2)")
    external = case.operation(seq=2, op_type_id="XT", op_type_name="Heat treatment", source="external",
                              supplier_id="XS1", ext_days=2, machine_id=None, operator_id=None)
    case.conn.commit()

    def run(key):
        accepted = case.accept(key=key)
        result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
        assert result["state"] == "complete", result
        return result["candidates"][0]["candidate_ref"]

    original = run("supplier-original-run-0001")
    first, _ = read_candidate_analysis(case.conn, original)
    assert first["metrics"]["changed_operation_count"]["value"] == 2
    assert first["metrics"]["machine_change_count"]["value"] == 0
    assert first["before_metrics"]["overdue_count"]["reason"]["code"] == "no_admission_baseline"
    base = {"candidate_ref": original}
    if adoption_source != "trial_candidate":
        adopter = service(case.conn)
        preview = adopter.preview(original)
        adopted = adopter.adopt(original, preview["write_context"]["write_token"], "supplier-adoption-0001", INTENT)
        assert adopted["ok"], adopted
        base = {"plan_ref": adopted["data"]["official_plan"]["plan_ref"]}
    if adoption_source.startswith("trial"):
        saved = saved_scenario(case, {"base": base}, changed=False, suffix="supplier")
        adopter = trial_adopter(case.conn)
        preview = adopter.preview(saved["scenario_ref"])
        adopted = adopter.adopt(saved["scenario_ref"], preview["write_context"]["write_token"], "supplier-trial-adoption", INTENT)
        assert adopted["ok"], adopted
    unchanged = run("supplier-unchanged-run-0002")
    comparison, _ = read_candidate_analysis(case.conn, unchanged)
    assert comparison["metrics"]["changed_operation_count"]["value"] == 0
    assert comparison["metrics"]["machine_change_count"]["value"] == 0
    assert comparison["operations"]["issues"] == []

    case.conn.execute("UPDATE Suppliers SET name='Renamed today' WHERE supplier_id='XS1'")
    case.conn.execute("UPDATE BatchOperations SET supplier_id='XS2' WHERE id=?", (external,))
    case.conn.commit()
    changed = run("supplier-changed-run-0003")
    baseline, _ = WorkbenchRunCandidateBaselineQueryService(case.conn).baseline(RunCandidateBaselineScope(changed))
    row = next(item for item in baseline["comparisons"] if item["candidate"]["source"] == "external")
    assert row["baseline_segments"][0]["source"] == "external"
    assert row["baseline_segments"][0]["supplier"] == {"ref": case.ref("supplier", "XS1"), "label": "Original supplier"}
    assert row["candidate"]["supplier"] == {"ref": case.ref("supplier", "XS2"), "label": "Second supplier"}
    assert row["delta"]["supplier_changed"] is True
    assert row["delta"]["machine_changed"] is False and row["delta"]["operator_changed"] is False
    comparison, _ = read_candidate_analysis(case.conn, changed)
    assert comparison["metrics"]["changed_operation_count"]["value"] == 1
    assert comparison["metrics"]["machine_change_count"]["value"] == 0
    if adoption_source == "candidate":
        frozen = deepcopy(comparison)
        audit = json.loads(case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=1").fetchone()[0])
        audit["proof"]["candidate_ref"] = changed
        case.conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=1", (json.dumps(audit),))
        case.conn.commit()
        baseline, _ = WorkbenchRunCandidateBaselineQueryService(case.conn).baseline(RunCandidateBaselineScope(changed))
        row = next(item for item in baseline["comparisons"] if item["candidate"]["source"] == "external")
        gaps = row["baseline_segments"][0]["data_gaps"]
        assert {item["code"] for item in gaps if item["field"] in ("source", "supplier")} == {"adoption_snapshot_invalid"}
        comparison, _ = read_candidate_analysis(case.conn, changed)
        assert comparison == frozen  # Current comparison keeps the original admission's audit.
        admitted_bad = run("supplier-bad-proof-run-0004")
        comparison, _ = read_candidate_analysis(case.conn, admitted_bad)
        issue = next(item for item in comparison["operations"]["issues"] if item["operation_ref"] == row["operation_ref"])
        assert {reason["code"] for reason in issue["reasons"]} == {"adoption_snapshot_invalid"}


def test_archived_resource_identity_survives_missing_display_directory(candidate_case):
    _, refs = compute(candidate_case)
    _, _, _, _, capture, _ = load_adoption_candidate(candidate_case.conn, refs[0])
    facts = GenerationFacts(capture)
    ref = facts.entity_refs["machine", "M1"]
    facts.tables["Machines"].clear()
    gaps = []
    resource = task_resource(facts, "machine", "M1", gaps)
    assert resource == {"ref": ref, "label": None}
    assert any(row["field"] == "machine" and row["code"] == "source_missing" for row in gaps)
    assert _resource_change({"machine": resource, "data_gaps": gaps},
                            {"machine": {"ref": ref, "label": "Known name"}, "data_gaps": []}, "machine") is False


def test_added_removed_and_absent_arrangements_are_known_without_counting_machine_reassignment():
    segment = {"row_ref": "original", "start": "2026-09-09T08:00:00", "end": "2026-09-09T09:00:00",
               "source": "internal", "machine": None, "operator": None, "supplier": None,
               "interval_comparable": True, "elapsed_hours": 1, "effective_processing_hours": None, "data_gaps": []}
    rows = [{"operation_ref": ref, "batch_ref": "batch", "selected_at_admission": True,
             "comparison_available": False, "status": status, "baseline_segments": segments}
            for ref, status, segments in (("added", "newly_scheduled", []), ("removed", "unscheduled", [segment]),
                                           ("absent", "unscheduled", []))]
    baseline = {"comparisons": rows, "rows_complete": True, "operation_count": 3, "full_operation_count": 3}
    metrics, operations = operation_metrics(baseline, ["batch"])
    assert metrics["changed_operation_count"]["value"] == 2
    assert metrics["machine_change_count"]["value"] == 0
    assert operations["changed_operation_refs"] == ["added", "removed"]
    assert operations["unknown_operation_refs"] == operations["machine_unknown_operation_refs"] == []


def test_arranged_and_unplanned_operations_share_one_sequence_order():
    def row(ref, sequence):
        return {"operation_ref": ref, "batch_ref": "b" * 48, "sequence": sequence}

    tasks = [row("t-unknown", None), row("t-big", "9007199254740993"), row("t-two", 2), row("t-zero", 0)]
    unplanned = [row("u-one", 1), row("u-unknown", None), row("u-zero", 0)]
    for order, expected_tasks, expected_unplanned in (
            ("asc", ["t-zero", "t-two", "t-big", "t-unknown"], ["u-zero", "u-one", "u-unknown"]),
            ("desc", ["t-unknown", "t-big", "t-two", "t-zero"], ["u-unknown", "u-one", "u-zero"])):
        arranged, pending = filter_workspace(tasks, unplanned, RunCandidateReadScope("c" * 48, order=order))
        assert [item["operation_ref"] for item in arranged] == expected_tasks
        assert [item["operation_ref"] for item in pending] == expected_unplanned


@pytest.mark.parametrize("reader", ("candidate_source", "candidate_workspace", "decision_operations", "admission_comparison",
                                    "adoption"))
def test_completed_candidate_receipt_without_dispositions_is_a_corrupt_record(candidate_case, reader):
    run_ref, refs = compute(candidate_case)
    conn = candidate_case.conn
    raw = conn.execute("SELECT result_json FROM WorkbenchRunReceipts WHERE run_ref=?", (run_ref,)).fetchone()[0]
    receipt = json.loads(raw)
    del receipt["dispositions"]
    corrupt_update(conn, "WorkbenchRunReceipts", "UPDATE WorkbenchRunReceipts SET result_json=? WHERE run_ref=?",
                   (json.dumps(receipt, ensure_ascii=False), run_ref))
    reads = {
        "candidate_source": lambda: read_candidate_source(CandidateStore(conn), refs[0]),
        "candidate_workspace": lambda: WorkbenchRunCandidateQueryService(conn).workspace(RunCandidateReadScope(refs[0])),
        "decision_operations": lambda: read_decision_details(conn, run_ref, "operations", selected_candidate_ref=refs[0]),
        "admission_comparison": lambda: WorkbenchRunCandidateBaselineQueryService(conn).baseline(
            RunCandidateBaselineScope(refs[0])),
        "adoption": lambda: load_adoption_candidate(conn, refs[0]),
    }
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        reads[reader]()
    assert rejected.value.code == "candidate_artifact_invalid"


@pytest.mark.parametrize("state", ("queued", "failed"))
def test_run_without_candidate_results_cannot_reread_its_admission_official_plan(candidate_case, state):
    from core.models.workbench_run_job import new_run_ref
    from core.services.workbench.facts.decision_read_model import build_failure_read_models
    from core.services.workbench.facts.decision_read_models import decode_model
    from core.services.workbench.run.decision_export import read_decision_export
    from data.repositories.workbench_run_repo import WorkbenchRunRepository

    conn = candidate_case.conn
    run_ref = candidate_case.accept(key="no-result-official-run-01")["run_ref"]
    if state == "failed":
        repo = WorkbenchRunRepository(conn)
        repo.claim(run_ref, new_run_ref(), "2026-09-10T12:00:01")
        failure = {"state": "failed", "result_persisted": False, "candidates": [],
                   "error": {"code": "fixture_saved_failure", "message": "Saved worker failure"}}
        repo.finish(run_ref, "failed", failure, "2026-09-10T12:00:02")
        admission = decode_model(repo.admission_read_model(run_ref, ("decision",)), ("decision",))["decision"]
        models = build_failure_read_models(repo.head(run_ref), admission, failure)
        repo.insert_decision_read_models(run_ref, models["run_model"], models["candidate_models"])
        conn.commit()
    # 只有产出候选结果的运行才保存工序处置；按原始来源重读排产时的正式计划需要它们。
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        read_decision_export(conn, run_ref, "recommendation", comparison_mode="admission_official")
    assert rejected.value.code == "candidate_baseline_invalid"

"""Real full Flask app integration plus terminal catalog and snapshot boundaries."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

import pytest
from flask import Blueprint

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_analysis import operation_metrics
from core.models.workbench_run_baseline import RunCandidateBaselineScope
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.facts.candidate_artifact import ARTIFACT_FIELDS
from core.services.workbench.facts.candidate_projection import (
    algorithm_facts,
    business_candidate_fields,
)
from core.services.workbench.facts.candidate_tasks import scope_workspace_tasks
from core.services.workbench.run.candidate_analysis import read_candidate_analysis
from core.services.workbench.run.candidate_baseline import WorkbenchRunCandidateBaselineQueryService
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests._support.excel_templates import point_env_at_shared
from tests.workbench.run_candidate_adoption_support import INTENT, service
from tests.workbench.run_candidate_support import BASE, api, compute, read, state
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.trial_adoption_support import saved_scenario
from tests.workbench.trial_adoption_support import service as trial_adopter
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401
from web.routes.workbench.run_candidate_baseline import register_run_candidate_baseline_routes
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
    from web.bootstrap.entrypoint import create_app
    app = create_app()
    bp = Blueprint("bl_full_app_candidates", __name__)
    register_run_candidate_routes(bp)
    app.register_blueprint(bp)
    client = app.test_client()
    before = state(case.conn)
    catalog = read(client, "/runs/" + run_ref + "/candidates")
    assert catalog["data"]["candidate_count"] == len(refs)
    expected_scope_keys = {
        "scheduled_operation_count", "complete_batch_count", "objective_scope", "components_known", "is_complete",
    }
    for item in catalog["data"]["candidates"]:
        for evaluation in item["evaluations"].values():
            scope = evaluation["scoring_scope"]
            assert set(scope) == expected_scope_keys
            assert type(scope["scheduled_operation_count"]) is int and type(scope["complete_batch_count"]) is int
    result = read(client, "/candidates/" + refs[0])
    generation = result["data"]["generation"]
    assert generation["baseline"] == {"baseline_ref": None, "version": None, "kind": "admission_official",
                                      "captured_at": generation["accepted_at"], "captured_task_count": 0}
    artifact = json.loads(case.conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=?", (refs[0],)).fetchone()[0])
    assert set(artifact) == set(ARTIFACT_FIELDS)
    assert artifact["validated_payload"] == {"scheduled_op_ids": [case.op_id]}
    assert artifact["metrics"]["completion"]["objective_scope"] == "all_batches"
    assert 1 <= len(refs) <= 3
    assert generation["algorithm"] == algorithm_facts(artifact, business_fields=business_candidate_fields(artifact))
    assert generation["algorithm"]["target_objectives"] == artifact["target_objectives"]
    assert list(artifact["evaluations"]) != artifact["target_objectives"]
    assert all(set(ev["scoring_scope"]) == expected_scope_keys for ev in generation["algorithm"]["evaluations"].values())
    analysis_res = client.get(BASE + "/candidates/" + refs[0] + "/analysis")
    assert analysis_res.status_code == 200, analysis_res.get_data(as_text=True)
    analysis = analysis_res.get_json()["data"]
    assert "batch_refs" not in analysis and analysis["batch_count"] == 1
    assert set(analysis["operations"]) == {"operation_count", "changed_operation_refs", "unknown_operation_refs", "issues"}
    assert analysis["operations"]["operation_count"] == 1
    token = result["meta"]["snapshot_ref"]
    from core.services.workbench.facts import candidate_read_source
    from core.services.workbench.run import candidates as run_candidates_service
    from web.routes.workbench import run_candidates

    with monkeypatch.context() as patch:
        patch.setattr(run_candidates, "candidate_response", lambda *_: pytest.fail("Downloads must not rehearse a discarded JSON envelope"))
        patch.setattr(
            candidate_read_source,
            "candidate_operation_effort_projection",
            lambda *_: pytest.fail("Candidate export must not project operation effort"),
        )
        patch.setattr(
            candidate_read_source,
            "candidate_gantt_graph",
            lambda *_, **__: pytest.fail("Candidate export must not build gantt graph"),
        )
        patch.setattr(
            run_candidates_service,
            "candidate_delivery_risks",
            lambda *_: pytest.fail("Candidate export must not compute delivery risks"),
        )
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
           "baseline_segment": {"source": "external", "data_gaps": []},
           "delta": {"start_hours": 2, "end_hours": 2, "machine_changed": None, "operator_changed": None,
                     "supplier_changed": None}}
    metrics, operations = operation_metrics([row])
    assert metrics["changed_operation_count"]["value"] == 1
    assert metrics["machine_change_count"]["value"] is None and metrics["machine_change_count"]["unknown_count"] == 1
    assert set(operations) == {"operation_count", "changed_operation_refs", "unknown_operation_refs", "issues"}
    assert operations["operation_count"] == 1 and operations["changed_operation_refs"] == ["op"]
    assert operations["unknown_operation_refs"] == []
    assert {reason["code"] for reason in operations["issues"][0]["reasons"]} == {
        "resource_identity_unavailable", "historical_supplier_not_recorded"}
    row["delta"].update(start_hours=0, end_hours=0)
    metrics, operations = operation_metrics([row])
    assert metrics["changed_operation_count"]["value"] is None
    assert operations["unknown_operation_refs"] == ["op"]
    row["candidate"]["source"] = "internal"
    row["baseline_segment"]["source"] = None
    row["delta"].update(machine_changed=False, operator_changed=False)
    metrics, operations = operation_metrics([row])
    assert metrics["changed_operation_count"]["value"] is None
    assert {reason["code"] for reason in operations["issues"][0]["reasons"]} == {"historical_source_unavailable"}
    row["delta"]["start_hours"] = 1
    metrics, _ = operation_metrics([row])
    assert metrics["changed_operation_count"]["value"] == 1


@pytest.mark.parametrize("adoption_source", ["candidate", "trial_candidate", "trial_plan"])
def test_adopted_external_supplier_uses_original_lineage_and_null_resources_are_known(trial_case, adoption_source):
    case = trial_case
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('XT','Heat treatment','external')")
    case.conn.executemany("INSERT INTO Suppliers(supplier_id,name,default_days) VALUES (?,?,2)",
                         (("XS1", "Original supplier"), ("XS2", "Second supplier")))
    case.conn.executemany("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES (?,'XT')", (("XS1",), ("XS2",)))
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                      "VALUES ('P1',2,'XT','Heat treatment','external','XS1',2)")
    external = case.operation(seq=2, op_type_id="XT", op_type_name="Heat treatment", source="external",
                              supplier_id="XS1", ext_days=2, machine_id=None, operator_id=None)
    case.conn.commit()

    def run(key):
        accepted = case.accept(key=key)
        result = WorkbenchRunWorker(case.conn, clock=datetime.now).execute(accepted["run_ref"])
        assert result["state"] == "complete", result
        return result["candidates"][0]["candidate_ref"]

    original = run("supplier-original-run-0001")
    first, _ = read_candidate_analysis(case.conn, original, bind_snapshot=lambda scope, state: state)
    assert "batch_refs" not in first and first["batch_count"] == 1
    assert first["operations"]["operation_count"] == 2
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
    comparison, _ = read_candidate_analysis(case.conn, unchanged, bind_snapshot=lambda scope, state: state)
    assert comparison["metrics"]["changed_operation_count"]["value"] == 0
    assert comparison["metrics"]["machine_change_count"]["value"] == 0
    assert comparison["operations"]["issues"] == []

    case.conn.execute("UPDATE Suppliers SET name='Renamed today' WHERE supplier_id='XS1'")
    case.conn.execute("UPDATE BatchOperations SET supplier_id='XS2' WHERE id=?", (external,))
    case.conn.commit()
    changed = run("supplier-changed-run-0003")
    baseline, _ = WorkbenchRunCandidateBaselineQueryService(case.conn).baseline(RunCandidateBaselineScope(changed), bind_snapshot=lambda scope, state: state)
    row = next(item for item in baseline["comparisons"] if item["candidate"]["source"] == "external")
    assert row["baseline_segment"]["source"] == "external"
    assert row["baseline_segment"]["supplier"] == {"ref": case.ref("supplier", "XS1"), "label": "Original supplier"}
    assert row["candidate"]["supplier"] == {"ref": case.ref("supplier", "XS2"), "label": "Second supplier"}
    assert row["delta"]["supplier_changed"] is True
    assert row["delta"]["machine_changed"] is False and row["delta"]["operator_changed"] is False
    comparison, _ = read_candidate_analysis(case.conn, changed, bind_snapshot=lambda scope, state: state)
    assert comparison["metrics"]["changed_operation_count"]["value"] == 1
    assert comparison["metrics"]["machine_change_count"]["value"] == 0


def test_added_removed_and_absent_arrangements_are_known_without_counting_machine_reassignment():
    segment = {"row_ref": "original", "start": "2026-09-09T08:00:00", "end": "2026-09-09T09:00:00",
               "source": "internal", "machine": None, "operator": None, "supplier": None,
               "elapsed_hours": 1, "effective_processing_hours": None, "data_gaps": []}
    rows = [{"operation_ref": ref, "batch_ref": "batch", "selected_at_admission": True,
             "comparison_available": False, "status": status, "baseline_segment": baseline_segment}
            for ref, status, baseline_segment in (("added", "newly_scheduled", None), ("removed", "unscheduled", segment),
                                                   ("absent", "unscheduled", None))]
    metrics, operations = operation_metrics(rows)
    assert metrics["changed_operation_count"]["value"] == 2
    assert metrics["machine_change_count"]["value"] == 0
    assert set(operations) == {"operation_count", "changed_operation_refs", "unknown_operation_refs", "issues"}
    assert operations["operation_count"] == 3
    assert operations["changed_operation_refs"] == ["added", "removed"]
    assert operations["unknown_operation_refs"] == []


def test_arranged_and_unplanned_operations_share_one_sequence_order():
    from types import SimpleNamespace

    def row(ref, sequence):
        return {"operation_ref": ref, "batch_ref": "b" * 48, "sequence": sequence}

    tasks = [row("t-unknown", None), row("t-big", "9007199254740993"), row("t-two", 2), row("t-zero", 0)]
    unplanned = [row("u-one", 1), row("u-unknown", None), row("u-zero", 0)]
    source = SimpleNamespace(
        facts=None,
        raw_tasks=tasks,
        disposition={},
        tasks=tasks,
        unplanned=unplanned,
    )
    for order, expected_tasks, expected_unplanned in (
            ("asc", ["t-zero", "t-two", "t-big", "t-unknown"], ["u-zero", "u-one", "u-unknown"]),
            ("desc", ["t-unknown", "t-big", "t-two", "t-zero"], ["u-unknown", "u-one", "u-zero"])):
        arranged, pending = scope_workspace_tasks(
            source, RunCandidateReadScope("c" * 48, order=order)
        )
        assert [item["operation_ref"] for item in arranged] == expected_tasks
        assert [item["operation_ref"] for item in pending] == expected_unplanned


@pytest.mark.parametrize("state", ("queued", "failed"))
def test_run_without_candidate_results_cannot_reread_its_admission_official_plan(candidate_case, state):
    from core.models.workbench_run_receipt import FailedReceipt
    from core.services.workbench.facts.decision_read_models import decode_model
    from core.services.workbench.run.decision_export import read_decision_export
    from core.services.workbench.run.decision_process import read_process_details
    from core.services.workbench.run.terminal import record_terminal_without_results
    from core.shared.refs import new_ref
    from data.repositories.workbench_run_repo import WorkbenchRunRepository

    conn = candidate_case.conn
    run_ref = candidate_case.accept(key="no-result-official-run-01")["run_ref"]
    if state == "failed":
        repo = WorkbenchRunRepository(conn)
        repo.claim(run_ref, new_ref(), "2026-09-10T12:00:01")
        failure = FailedReceipt("failed", {"code": "fixture_saved_failure", "message": "Saved worker failure"}, None)
        admission = decode_model(repo.admission_read_model(run_ref, ("decision",)), ("decision",))["decision"]
        record_terminal_without_results(conn, repo.head(run_ref), admission, failure, "2026-09-10T12:00:02")
        conn.commit()
    # 只有产出候选结果的运行才保存工序处置；按原始来源重读排产时的正式计划需要它们。
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        read_decision_export(conn, run_ref, "recommendation", bind_snapshot=lambda scope, state: state, comparison_mode="admission_official")
    assert rejected.value.code == "candidate_baseline_invalid"
    # 没有候选就没有过程 anchor：过程查看和整份导出都在解析 anchor 时返回 404，不读取过程存档。
    statements = []
    conn.set_trace_callback(statements.append)
    try:
        for read in (lambda: read_process_details(conn, run_ref, bind_snapshot=lambda scope, state: state),
                     lambda: read_decision_export(conn, run_ref, "all", bind_snapshot=lambda scope, state: state)):
            with pytest.raises(WorkbenchCommandRejected) as missing:
                read()
            assert (missing.value.code, missing.value.status, str(missing.value)) == (
                "entity_not_found", 404, "这次排产还没有保存候选计算记录。")
    finally:
        conn.set_trace_callback(None)
    assert not any("PROCESS_JSON" in sql.upper() for sql in statements)


def test_due_projection_preserves_state_and_issue_across_candidate_baseline_and_reference(candidate_case, monkeypatch):
    case = candidate_case
    case.conn.execute("UPDATE Batches SET due_date='2026-10-16' WHERE batch_id='B1'")
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.1 WHERE id=?", (case.op_id,))
    for code, initial_due in (
        ("B_NULL", None),
        ("B_UNSPEC", "9999-12-31"),
        ("B_EMPTY", "2026-10-17"),
        ("B_SPACE", "2026-10-20"),
        ("B_TS", "2026-10-21"),
        ("B_BAD", "2026-10-18"),
        ("B_BLOB", "2026-10-19"),
    ):
        case.batch(code, due_date=initial_due)
        case.operation(code, unit_hours=0.1)
    case.conn.commit()

    accepted_v1 = case.accept(
        key="due-projection-v1-run-001",
        settings=case.settings("B1", "B_NULL", "B_UNSPEC", "B_EMPTY", "B_SPACE", "B_TS", "B_BAD", "B_BLOB"),
    )
    first_run = WorkbenchRunWorker(case.conn, clock=datetime.now).execute(accepted_v1["run_ref"])
    assert first_run["state"] == "complete", first_run
    first_cand = first_run["candidates"][0]["candidate_ref"]
    adopter = service(case.conn)
    preview = adopter.preview(first_cand)
    adopted = adopter.adopt(first_cand, preview["write_context"]["write_token"], "due-projection-adopt-001", INTENT)
    assert adopted["ok"], adopted

    case.conn.execute("UPDATE Batches SET due_date='' WHERE batch_id='B_EMPTY'")
    case.conn.execute("UPDATE Batches SET due_date='   ' WHERE batch_id='B_SPACE'")
    case.conn.execute("UPDATE Batches SET due_date='2026-10-21 12:30:00' WHERE batch_id='B_TS'")
    case.conn.execute("UPDATE Batches SET due_date='2026-02-30' WHERE batch_id='B_BAD'")
    case.conn.execute("UPDATE Batches SET due_date=? WHERE batch_id='B_BLOB'", (b"bad-due",))
    for code in ("B1", "B_NULL", "B_UNSPEC"):
        case.operation(code, seq=2, unit_hours=0.1, status="skipped")
    case.conn.commit()

    accepted_v2 = case.accept(
        key="due-projection-v2-run-002",
        settings=case.settings("B1", "B_NULL", "B_UNSPEC"),
    )
    second_run = WorkbenchRunWorker(case.conn, clock=datetime.now).execute(accepted_v2["run_ref"])
    assert second_run["state"] in ("complete", "partial"), second_run
    run_ref = second_run["run_ref"]
    cand_ref = second_run["candidates"][0]["candidate_ref"]

    bp = Blueprint("bl_due_projection_baseline", __name__)
    register_run_candidate_baseline_routes(bp)
    case.app.register_blueprint(bp)
    client, _ = api(case)

    def due_projection(rows):
        return {
            (row["batch_label"], row["sequence"]): (
                row["due_date"],
                row["due_state"],
                row["due_issue"],
                [item["code"] for item in row["data_gaps"] if item["field"] == "due_date"],
            )
            for row in rows
        }

    def delivery_due_projection(items):
        return {
            row["batch_id"]: (row["due_date"], row["due_state"], row["due_issue"])
            for row in items
        }

    expected_selected = {
        "B1": ("2026-10-16", "specified", None, []),
        "B_NULL": (None, "invalid", "due_date_missing", ["not_recorded"]),
        "B_UNSPEC": ("9999-12-31", "unspecified", None, []),
    }
    expected_all = {
        **expected_selected,
        "B_EMPTY": (None, "invalid", "due_date_missing", ["not_recorded"]),
        "B_SPACE": (None, "invalid", "due_date_invalid", ["invalid_stored_value"]),
        "B_TS": (None, "invalid", "due_date_invalid", ["invalid_stored_value"]),
        "B_BAD": (None, "invalid", "due_date_invalid", ["invalid_stored_value"]),
        "B_BLOB": (None, "invalid", "due_date_invalid", ["blob_metadata"]),
    }

    def get_data(path, **query):
        response = client.get(BASE + path, query_string=query)
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.headers["Cache-Control"] == "no-store"
        return response.get_json()["data"]

    workspace = read(client, f"/candidates/{cand_ref}/workspace")["data"]
    assert due_projection(workspace["tasks"]) == {(code, 1): val for code, val in expected_selected.items()}
    assert due_projection(workspace["unplanned_operations"]) == {(code, 2): val for code, val in expected_selected.items()}
    assert delivery_due_projection(workspace["delivery_risks"]["items"]) == {
        row["batch_label"]: (row["due_date"], row["due_state"], row["due_issue"])
        for row in workspace["tasks"]
    }

    baseline = get_data(f"/candidates/{cand_ref}/baseline")
    expected_comparisons = {
        **{(code, 1): val for code, val in expected_all.items()},
        **{(code, 2): val for code, val in expected_selected.items()},
    }
    assert due_projection(baseline["comparisons"]) == expected_comparisons

    reference_ws = get_data(
        f"/runs/{run_ref}/decision/reference-workspace",
        comparison_mode="admission_official",
        selected_candidate_ref=cand_ref,
        resource_view="full_candidate",
    )
    assert due_projection(reference_ws["tasks"]) == {(code, 1): val for code, val in expected_all.items()}
    assert due_projection(reference_ws["unplanned_operations"]) == {(code, 2): val for code, val in expected_selected.items()}
    assert delivery_due_projection(reference_ws["delivery_risks"]["items"]) == {
        row["batch_label"]: (row["due_date"], row["due_state"], row["due_issue"])
        for row in reference_ws["tasks"]
    }

    from core.services.workbench.facts.candidate_facts import GenerationFacts
    from core.services.workbench.facts.candidate_tasks import operation_labels
    from core.services.workbench.facts.production_capture import ProductionFactsCapture
    from data.repositories.workbench_run_candidate_repo import WorkbenchRunCandidateRepository

    saved_capture = WorkbenchRunCandidateRepository(case.conn).job_capture(run_ref)
    assert saved_capture is not None
    execution_rows = json.loads(saved_capture["execution_json"])
    archive = ProductionFactsCapture(case.conn).scoped_archive(
        json.loads(saved_capture["normalized_input_json"])["batch_refs"],
        baseline_version=json.loads(saved_capture["baseline_json"])["version"],
    )
    persisted_archive = json.loads(saved_capture["conditions_archive_json"])
    memory_facts = GenerationFacts({"facts": archive, "execution": execution_rows})
    persisted_facts = GenerationFacts({"facts": persisted_archive, "execution": execution_rows})
    assert isinstance(memory_facts.tables["Batches"]["B_BLOB"]["due_date"], bytes)
    assert persisted_facts.tables["Batches"]["B_BLOB"]["due_date"] == {"$sqlite_blob": "YmFkLWR1ZQ=="}
    blob_op_id = next(
        op_id for op_id, row in memory_facts.tables["BatchOperations"].items() if row["batch_id"] == "B_BLOB"
    )
    blob_op_ref = memory_facts.operation_refs[blob_op_id]
    memory_blob_labels, _ = operation_labels(memory_facts, blob_op_ref)
    persisted_blob_labels, _ = operation_labels(persisted_facts, blob_op_ref)
    assert (
        memory_blob_labels["due_date"],
        memory_blob_labels["due_state"],
        memory_blob_labels["due_issue"],
        memory_blob_labels["data_gaps"],
    ) == (
        persisted_blob_labels["due_date"],
        persisted_blob_labels["due_state"],
        persisted_blob_labels["due_issue"],
        persisted_blob_labels["data_gaps"],
    ) == (
        None,
        "invalid",
        "due_date_invalid",
        [{"field": "due_date", "code": "blob_metadata", "message": "排产时这一项的记录格式无法显示，请联系维护人员核对。"}],
    )

    original_capture = WorkbenchRunCandidateRepository.job_capture
    overrides = {
        "B1": "",
        "B_NULL": "2026-02-30",
        "B_UNSPEC": {"$sqlite_blob": "YmFkLWR1ZQ=="},
    }

    def archived_damaged_capture(repo_self, target_run_ref):
        row = original_capture(repo_self, target_run_ref)
        if row is None or target_run_ref != run_ref:
            return row
        facts = json.loads(row["conditions_archive_json"])
        cols = facts["columns"]["Batches"]
        batch_idx, due_idx = cols.index("batch_id"), cols.index("due_date")
        for batch_row in facts["tables"]["Batches"]:
            if batch_row[batch_idx] in overrides:
                batch_row[due_idx] = overrides[batch_row[batch_idx]]
        patched_text = json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
        return {
            **row,
            "conditions_archive_json": patched_text,
            "conditions_archive_bytes": len(patched_text.encode("utf-8")),
        }

    monkeypatch.setattr(WorkbenchRunCandidateRepository, "job_capture", archived_damaged_capture)
    damaged_ws = read(client, f"/candidates/{cand_ref}/workspace")["data"]
    expected_damaged = {
        "B1": (None, "invalid", "due_date_missing", ["not_recorded"]),
        "B_NULL": (None, "invalid", "due_date_invalid", ["invalid_stored_value"]),
        "B_UNSPEC": (None, "invalid", "due_date_invalid", ["blob_metadata"]),
    }
    assert due_projection(damaged_ws["tasks"]) == {(code, 1): val for code, val in expected_damaged.items()}
    assert due_projection(damaged_ws["unplanned_operations"]) == {(code, 2): val for code, val in expected_damaged.items()}
    assert delivery_due_projection(damaged_ws["delivery_risks"]["items"]) == {
        row["batch_label"]: (row["due_date"], row["due_state"], row["due_issue"])
        for row in damaged_ws["tasks"]
    }
    damaged_baseline = get_data(f"/candidates/{cand_ref}/baseline")
    damaged_ref_ws = get_data(
        f"/runs/{run_ref}/decision/reference-workspace",
        comparison_mode="admission_official",
        selected_candidate_ref=cand_ref,
        resource_view="full_candidate",
    )
    for code, expected_val in expected_damaged.items():
        assert due_projection(damaged_baseline["comparisons"])[(code, 1)] == expected_val
        assert due_projection(damaged_baseline["comparisons"])[(code, 2)] == expected_val
        assert due_projection(damaged_ref_ws["tasks"])[(code, 1)] == expected_val
        assert due_projection(damaged_ref_ws["unplanned_operations"])[(code, 2)] == expected_val

    overrides.update(B1="   ", B_NULL="2026-10-16 12:30:00")
    whitespace_ws = read(client, f"/candidates/{cand_ref}/workspace")["data"]
    expected_whitespace = {
        "B1": (None, "invalid", "due_date_invalid", ["invalid_stored_value"]),
        "B_NULL": (None, "invalid", "due_date_invalid", ["invalid_stored_value"]),
        "B_UNSPEC": (None, "invalid", "due_date_invalid", ["blob_metadata"]),
    }
    assert due_projection(whitespace_ws["tasks"]) == {(code, 1): val for code, val in expected_whitespace.items()}
    assert due_projection(whitespace_ws["unplanned_operations"]) == {(code, 2): val for code, val in expected_whitespace.items()}
    assert delivery_due_projection(whitespace_ws["delivery_risks"]["items"]) == {
        row["batch_label"]: (row["due_date"], row["due_state"], row["due_issue"])
        for row in whitespace_ws["tasks"]
    }


_PROFILE = {"slug": "v2_generated", "candidate_origin": "graph_ready_v2_generated"}
_ARTIFACT_DAMAGE = {
    "missing_top_level_key": lambda artifact: artifact.pop("evaluations"),
    "earlier_shape_key": lambda artifact: artifact.update(generation_policy_version="unified_search_v1"),
    "earlier_strategy_key": lambda artifact: artifact.update(used_strategy=artifact["sort_strategy"]),
    "missing_completion_scope": lambda artifact: artifact["metrics"]["completion"].pop("objective_scope"),
    "summary_not_object": lambda artifact: artifact.update(summary=[]),
    "result_trace_missing_key": lambda artifact: artifact["results"][0].pop("seed_source"),
    "result_trace_earlier_type_key": lambda artifact: artifact["results"][0].update(op_type_id="T1"),
    "earlier_payload_key": lambda artifact: artifact["validated_payload"].update(validation_errors=[]),
    # The values readers show as they are: they were a "data gap" on the card, the artifact is corrupt instead.
    "label_not_text": lambda artifact: artifact.update(label=7),
    "algo_mode_not_a_choice": lambda artifact: artifact.update(algo_mode="balanced"),
    "strategy_not_recorded": lambda artifact: artifact.update(sort_strategy=None),
    "shown_count_not_integer": lambda artifact: artifact["metrics"].update(changeover_count=1.5),
    "shown_hours_negative": lambda artifact: artifact["metrics"].update(total_tardiness_hours=-0.5),
    "utilisation_flag_not_bool": lambda artifact: artifact["metrics"].update(util_defined=1),
    "incomplete_batch_id_not_text": lambda artifact: artifact["metrics"]["completion"].update(incomplete_batch_ids=[""]),
    # The chosen plan's settings, as history conditions and the generation card show and compare them.
    "sequence_not_integer": lambda artifact: artifact.update(sequence=float(artifact["sequence"])),
    "used_params_not_object": lambda artifact: artifact.update(used_params=None),
    "dispatch_mode_not_a_choice": lambda artifact: artifact.update(dispatch_mode="balanced"),
    "budget_not_positive": lambda artifact: artifact.update(time_budget_seconds=0),
    # The objective, the directions derived from it and the business facts tied to those directions.
    "objective_not_a_choice": lambda artifact: artifact.update(objective_name="min_cost"),
    "targets_not_the_objective_directions": lambda artifact: artifact["target_objectives"].reverse(),
    "representatives_not_a_list": lambda artifact: artifact.update(representative_objectives=None),
    "representative_not_a_target": lambda artifact: artifact.update(representative_objectives=["min_cost"]),
    "representative_repeated": lambda artifact: artifact.update(
        representative_objectives=artifact["target_objectives"][:1] * 2),
    "evaluation_missing_for_a_target": lambda artifact: artifact["evaluations"].pop(artifact["target_objectives"][-1]),
    "evaluation_missing_its_scope": lambda artifact: artifact["evaluations"][artifact["objective_name"]].pop("scoring_scope"),
    "scoring_scope_not_a_choice": lambda artifact: artifact["evaluations"][artifact["objective_name"]]["scoring_scope"]
        .update(objective_scope="some_batches"),
    "scoring_scope_count_not_integer": lambda artifact: artifact["evaluations"][artifact["objective_name"]]["scoring_scope"]
        .update(complete_batch_count=1.0),
    "scoring_scope_flag_not_bool": lambda artifact: artifact["evaluations"][artifact["objective_name"]]["scoring_scope"]
        .update(is_complete=1),
    "origin_not_recorded": lambda artifact: artifact.update(origin=None),
    "origin_direction_not_a_target": lambda artifact: artifact["origin"].update(search_objective="min_cost"),
    "origin_missing_its_request": lambda artifact: artifact["origin"].pop("request_id"),
    "origin_earlier_shape_key": lambda artifact: artifact["origin"].update(stage="initial"),
    # The graph-ready profile is in the origin exactly when the plan decoded with one.
    "origin_profile_without_the_plans": lambda artifact: artifact["origin"].update(graph_ready_profile=_PROFILE),
    "plan_profile_missing_from_origin": lambda artifact: artifact["used_params"].update(graph_ready_profile=_PROFILE),
    "first_found_not_integer": lambda artifact: artifact.update(first_found_elapsed_ms=1.5),
    "search_reference_not_object": lambda artifact: artifact.update(search_evidence_ref=None),
    "search_reference_missing_run": lambda artifact: artifact["search_evidence_ref"].pop("run_ref"),
    "search_event_not_positive": lambda artifact: artifact["search_evidence_ref"].update(source_event_id=0),
    # The decode outcome adoption proves and the validated operations the task rows carry.
    "summary_success_not_bool": lambda artifact: artifact["summary"].update(success="yes"),
    "summary_errors_not_list": lambda artifact: artifact["summary"].update(errors=None),
    "summary_count_negative": lambda artifact: artifact["summary"].update(failed_ops=-1),
    "validated_operation_not_identity": lambda artifact: artifact["validated_payload"].update(
        scheduled_op_ids=[str(op_id) for op_id in artifact["validated_payload"]["scheduled_op_ids"]]),
    "validated_operation_repeated": lambda artifact: artifact["validated_payload"]["scheduled_op_ids"].extend(
        artifact["validated_payload"]["scheduled_op_ids"]),
    "result_trace_not_validated": lambda artifact: artifact["results"][0].update(op_id=artifact["results"][0]["op_id"] + 1000),
    # The facts the artifact repeats from its candidate row.
    "sequence_not_the_rows": lambda artifact: artifact.update(sequence=artifact["sequence"] + 1),
    "validated_operations_not_the_task_rows": lambda artifact: _drop_validated_operation(artifact),
}


def _drop_validated_operation(artifact):
    """One validated operation fewer, with its trace: consistent in itself, one short of the row's task count."""
    op_id = artifact["validated_payload"]["scheduled_op_ids"].pop()
    artifact["results"] = [row for row in artifact["results"] if row["op_id"] != op_id]


def _serve_stored_artifact(monkeypatch, change):
    """Hand every stored candidate read the artifact as the repository returns it, with one cell changed."""
    from data.repositories.workbench_run_candidate_repo import WorkbenchRunCandidateRepository

    one, many = WorkbenchRunCandidateRepository.candidate_row, WorkbenchRunCandidateRepository.candidate_rows

    def changed(row):
        artifact = json.loads(row[4])
        change(artifact)
        text = json.dumps(artifact, ensure_ascii=False, separators=(",", ":"))
        return row[:4] + (text, len(text.encode("utf-8")))

    monkeypatch.setattr(WorkbenchRunCandidateRepository, "candidate_row",
                        lambda repo, candidate_ref: changed(one(repo, candidate_ref)))
    monkeypatch.setattr(WorkbenchRunCandidateRepository, "candidate_rows",
                        lambda repo, run_ref, limit: (changed(row) for row in many(repo, run_ref, limit)))


@pytest.mark.parametrize("damage", sorted(_ARTIFACT_DAMAGE))
def test_stored_artifact_is_admitted_once_at_the_candidate_read_boundary(candidate_case, monkeypatch, damage):
    from core.services.workbench.facts.candidate_store import CandidateStore

    case = candidate_case
    _run_ref, refs = compute(case)
    _serve_stored_artifact(monkeypatch, _ARTIFACT_DAMAGE[damage])
    store = CandidateStore(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as rejected, store.snapshot():
        store.candidate(refs[0])
    assert (rejected.value.code, rejected.value.status) == ("candidate_artifact_invalid", 500)


def _graph_profile(artifact):
    artifact["used_params"]["graph_ready_profile"] = artifact["origin"]["graph_ready_profile"] = _PROFILE
    return {"origin": artifact["origin"]}


def _repair_recorded(artifact):
    artifact["origin"].update(repair_decision={"kind": "swap"}, source_event_ref=None)
    return {"origin": artifact["origin"]}


def _no_representative(artifact):
    artifact["representative_objectives"] = []
    return {"representative_objectives": []}


def _found_at_start(artifact):
    artifact["first_found_elapsed_ms"] = 0
    return {"first_found_elapsed_ms": 0}


def _event_not_recorded(artifact):
    artifact["search_evidence_ref"]["source_event_id"] = None
    return {"search_evidence_ref": artifact["search_evidence_ref"]}


# Legal stored forms the writer produces besides the fixture's own: each one reads back as it was saved.
_ARTIFACT_LEGAL = {
    "origin_with_graph_profile": _graph_profile,
    "origin_with_repair_and_no_source_event": _repair_recorded,
    "no_representative_direction": _no_representative,
    "first_found_at_start": _found_at_start,
    "search_event_not_recorded": _event_not_recorded,
}


def test_task_rows_are_as_many_as_the_candidate_row_counts(candidate_case, monkeypatch):
    from core.services.workbench.facts.candidate_store import CandidateStore
    from data.repositories.workbench_run_candidate_repo import WorkbenchRunCandidateRepository

    case = candidate_case
    _run_ref, refs = compute(case)
    stored = WorkbenchRunCandidateRepository.task_rows
    monkeypatch.setattr(WorkbenchRunCandidateRepository, "task_rows",
                        lambda repo, candidate_ref, limit: list(stored(repo, candidate_ref, limit))[:-1])
    store = CandidateStore(case.conn)
    with store.snapshot():
        store.candidate(refs[0])
        with pytest.raises(WorkbenchCommandRejected) as rejected:
            store.tasks(refs[0])
    assert (rejected.value.code, rejected.value.status) == ("candidate_artifact_invalid", 500)


def _external_operation(case):
    """B1's second operation, external: a new decode of it records no operation type of its own."""
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('XT','Heat treatment','external')")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,default_days) VALUES ('XS1','First supplier',2)")
    case.conn.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('XS1','XT')")
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                      "VALUES ('P1',2,'XT','Heat treatment','external','XS1',2)")
    external = case.operation(seq=2, op_type_id="XT", op_type_name="Heat treatment", source="external",
                              supplier_id="XS1", ext_days=2, machine_id=None, operator_id=None)
    case.conn.commit()
    return external


def test_external_operations_reach_the_official_plan_with_their_archived_type(trial_case, monkeypatch):
    """Candidate and trial adoptions take every operation's type from its archived operation, decoded or seeded."""
    from core.services.workbench.facts.candidate_store import CandidateStore

    case = trial_case
    external = _external_operation(case)
    expected = (case.ref("op_type", "XT"), "Heat treatment")

    def run(key, settings=None):
        accepted = case.accept(key=key, settings=settings)
        return WorkbenchRunWorker(case.conn, clock=datetime.now).execute(accepted["run_ref"])["candidates"][0]["candidate_ref"]

    def official_type(adopted):
        version = adopted["data"]["official_plan"]["version"]
        return tuple(case.conn.execute("SELECT op_type_ref, op_type_label FROM Schedule WHERE version=? AND op_id=?",
                                       (version, external)).fetchone())

    def adopt_trial(candidate_ref, suffix):
        saved = saved_scenario(case, {"base": {"candidate_ref": candidate_ref}}, changed=False, suffix=suffix)
        adopter = trial_adopter(case.conn)
        token = adopter.preview(saved["scenario_ref"])["write_context"]["write_token"]
        return adopter.adopt(saved["scenario_ref"], token, "external-type-trial-" + suffix, INTENT)

    decoded = run("external-type-run-000001")
    client, _ = api(case)
    task = next(row for row in read(client, "/candidates/" + decoded)["data"]["tasks"] if row["source"] == "external")
    assert (task["process_type_ref"], task["process_type_label"]) == expected
    adopter = service(case.conn)
    token = adopter.preview(decoded)["write_context"]["write_token"]
    assert official_type(adopter.adopt(decoded, token, "external-type-adoption-0001", INTENT)) == expected
    assert official_type(adopt_trial(run("external-type-run-000002"), "decoded")) == expected
    # The next run freezes the adopted external operation; its trace's seed record plays no part in its type.
    case.config(freeze_window_enabled="yes", freeze_window_days=3)
    case.batch("B2")
    case.operation("B2", setup_hours=0, unit_hours=1)
    case.conn.commit()
    seeded = run("external-type-run-000003", case.settings("B1", "B2"))
    store = CandidateStore(case.conn)
    with store.snapshot():
        trace = next(row for row in store.candidate(seeded)["artifact"]["results"] if row["op_id"] == external)
    assert trace["seed_source"] == "freeze_window"
    _serve_stored_artifact(monkeypatch, lambda artifact: [
        row.update(seed_source=None) for row in artifact["results"] if row["op_id"] == external])
    assert official_type(adopt_trial(seeded, "seeded")) == expected


def _serve_archived_facts(monkeypatch, change):
    """Hand every capture read its archived production facts as the repository returns them, with one cell changed."""
    from data.repositories.workbench_run_candidate_repo import WorkbenchRunCandidateRepository

    stored = WorkbenchRunCandidateRepository.job_capture

    def changed(repo, run_ref):
        row = dict(stored(repo, run_ref))
        facts = json.loads(row["conditions_archive_json"])
        change(facts)
        row["conditions_archive_json"] = text = json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
        row["conditions_archive_bytes"] = len(text.encode("utf-8"))
        return row

    monkeypatch.setattr(WorkbenchRunCandidateRepository, "job_capture", changed)


def _set_archived_cell(facts, table, match, column, value):
    columns = facts["columns"][table]
    (row,) = [row for row in facts["tables"][table]
              if all(row[columns.index(key)] == expected for key, expected in match.items())]
    row[columns.index(column)] = value


_ARCHIVED_TYPE_DAMAGE = {
    "arranged_operation_untyped": lambda facts, op_id: _set_archived_cell(
        facts, "BatchOperations", {"id": op_id}, "op_type_id", None),
    "type_ref_retired": lambda facts, op_id: _set_archived_cell(
        facts, "WorkbenchEntityRefs", {"kind": "op_type", "entity_key": "T1", "active": 1}, "active", 0),
}


@pytest.mark.parametrize("damage", sorted(_ARCHIVED_TYPE_DAMAGE))
def test_archived_type_identity_damage_fails_loudly_before_the_official_plan(candidate_case, monkeypatch, damage):
    from core.services.workbench.run.candidate_adoption_validation import validate_adoption

    case = candidate_case
    _run_ref, refs = compute(case)
    _serve_archived_facts(monkeypatch, lambda facts: _ARCHIVED_TYPE_DAMAGE[damage](facts, case.op_id))
    client, _ = api(case)
    assert client.get(BASE + "/candidates/" + refs[0]).status_code == 500
    for adoption in (lambda: validate_adoption(case.conn, refs[0]), lambda: service(case.conn).preview(refs[0])):
        with pytest.raises((KeyError, WorkbenchCommandRejected)) as failed:
            adoption()
        assert type(failed.value) is KeyError or failed.value.status == 500
    assert case.conn.execute("SELECT COUNT(*) FROM Schedule").fetchone()[0] == 0


def test_untyped_operation_has_no_type_identity(candidate_case):
    """An operation without a type (the column is nullable) reads with neither a type ref nor a type name."""
    from core.services.workbench.facts.candidate_facts import GenerationFacts
    from core.services.workbench.facts.candidate_store import CandidateStore
    from core.services.workbench.facts.candidate_tasks import operation_labels

    case = candidate_case
    _run_ref, refs = compute(case)
    store = CandidateStore(case.conn)
    with store.snapshot():
        capture = store.capture(store.candidate_run(refs[0]))
    facts = GenerationFacts(capture)
    facts.tables["BatchOperations"][case.op_id]["op_type_id"] = None
    labels, _ = operation_labels(facts, facts.operation_refs[case.op_id])
    assert (labels["process_type_ref"], labels["process_type_label"]) == (None, None)


@pytest.mark.parametrize("form", sorted(_ARTIFACT_LEGAL))
def test_legal_stored_artifact_forms_read_back_unchanged(candidate_case, monkeypatch, form):
    case = candidate_case
    _run_ref, refs = compute(case)
    expected = {}
    _serve_stored_artifact(monkeypatch, lambda artifact: expected.update(_ARTIFACT_LEGAL[form](artifact)))
    client, _ = api(case)
    algorithm = read(client, "/candidates/" + refs[0])["data"]["generation"]["algorithm"]
    assert {key: algorithm[key] for key in expected} == expected

"""Real full Flask app integration plus terminal catalog and snapshot boundaries."""

import json
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

import pytest
from flask import Blueprint

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_analysis import operation_metrics
from core.models.workbench_run_baseline import RunCandidateBaselineScope
from core.models.workbench_run_candidate import RunCandidateReadScope
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
    result = read(client, "/candidates/" + refs[0])
    generation = result["data"]["generation"]
    assert generation["baseline"] == {"baseline_ref": None, "version": None, "kind": "admission_official",
                                      "captured_at": generation["accepted_at"], "captured_task_count": 0}
    artifact = json.loads(case.conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=?", (refs[0],)).fetchone()[0])
    assert artifact["generation_policy_version"] == "unified_search_v1"
    assert 1 <= len(refs) <= 3
    assert generation["algorithm"] == algorithm_facts(artifact, business_fields=business_candidate_fields(artifact))
    assert generation["algorithm"]["target_objectives"] == artifact["target_objectives"]
    assert list(artifact["evaluations"]) != artifact["target_objectives"]
    token = result["meta"]["snapshot_ref"]
    from core.services.workbench.facts import candidate_read_source
    from core.services.workbench.run import candidates as run_candidates_service
    from web.routes.workbench import run_candidates

    with monkeypatch.context() as patch:
        patch.setattr(run_candidates, "_response", lambda *_: pytest.fail("Downloads must not rehearse a discarded JSON envelope"))
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
        result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
        assert result["state"] == "complete", result
        return result["candidates"][0]["candidate_ref"]

    original = run("supplier-original-run-0001")
    first, _ = read_candidate_analysis(case.conn, original, bind_snapshot=lambda scope, state: state)
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
    assert row["baseline_segments"][0]["source"] == "external"
    assert row["baseline_segments"][0]["supplier"] == {"ref": case.ref("supplier", "XS1"), "label": "Original supplier"}
    assert row["candidate"]["supplier"] == {"ref": case.ref("supplier", "XS2"), "label": "Second supplier"}
    assert row["delta"]["supplier_changed"] is True
    assert row["delta"]["machine_changed"] is False and row["delta"]["operator_changed"] is False
    comparison, _ = read_candidate_analysis(case.conn, changed, bind_snapshot=lambda scope, state: state)
    assert comparison["metrics"]["changed_operation_count"]["value"] == 1
    assert comparison["metrics"]["machine_change_count"]["value"] == 0


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
    from core.models.workbench_run_job import new_run_ref
    from core.services.workbench.facts.decision_read_model import build_failure_read_models
    from core.services.workbench.facts.decision_read_models import decode_model
    from core.services.workbench.run.decision_export import read_decision_export
    from core.services.workbench.run.decision_process import read_process_details
    from data.repositories.workbench_run_repo import WorkbenchRunRepository

    conn = candidate_case.conn
    run_ref = candidate_case.accept(key="no-result-official-run-01")["run_ref"]
    if state == "failed":
        repo = WorkbenchRunRepository(conn)
        repo.claim(run_ref, new_run_ref(), "2026-09-10T12:00:01")
        failure = {"state": "failed", "result_persisted": False, "candidates": [],
                   "error": {"code": "fixture_saved_failure", "message": "Saved worker failure"}}
        repo.finish(run_ref, failure, "2026-09-10T12:00:02")
        admission = decode_model(repo.admission_read_model(run_ref, ("decision",)), ("decision",))["decision"]
        models = build_failure_read_models(repo.head(run_ref), admission, failure)
        repo.insert_decision_read_models(run_ref, models["run_model"], models["candidate_models"])
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
    first_run = WorkbenchRunWorker(case.conn).execute(accepted_v1["run_ref"])
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
    second_run = WorkbenchRunWorker(case.conn).execute(accepted_v2["run_ref"])
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
    execution_rows = json.loads(saved_capture[1])
    archive = ProductionFactsCapture(case.conn).archive()
    facts_json = saved_capture[3]
    memory_facts = GenerationFacts({"facts": archive, "execution": execution_rows})
    persisted_facts = GenerationFacts({"facts_text": facts_json, "execution": execution_rows})
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
        facts = json.loads(row[3])
        cols = facts["columns"]["Batches"]
        batch_idx, due_idx = cols.index("batch_id"), cols.index("due_date")
        for batch_row in facts["tables"]["Batches"]:
            if isinstance(batch_row, list) and batch_row[batch_idx] in overrides:
                batch_row[due_idx] = overrides[batch_row[batch_idx]]
            elif isinstance(batch_row, dict) and batch_row["batch_id"] in overrides:
                batch_row["due_date"] = overrides[batch_row["batch_id"]]
        patched_text = json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
        return (*row[:3], patched_text, *row[4:7], len(patched_text.encode("utf-8")))

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

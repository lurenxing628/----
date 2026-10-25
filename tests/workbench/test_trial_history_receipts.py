"""Lossless trial receipts share their permanent history instead of duplicating it."""

import json
import sqlite3
from collections import Counter

import pytest
from flask import Blueprint

from core.infrastructure.transaction import TransactionManager
from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.plan.read_context import PlanReadContext
from core.services.workbench.trial.adoption_history import WorkbenchTrialAdoptionHistoryService
from core.services.workbench.trial.adoption_history_evidence import audit_fields, json_object
from data.repositories import workbench_plan_identity_repo
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_trial_repo import HISTORY_REFERENCE_FORMAT, WorkbenchTrialRepository
from tests.workbench.trial_adoption_support import INTENT, preview, saved_scenario
from tests.workbench.trial_adoption_support import service as adoption_service
from tests.workbench.trial_support import api, change, create, service
from tests.workbench.trial_support import trial_case as trial_case
from web.routes.workbench.materials import register_material_routes


def test_change_receipts_replay_original_full_history_through_every_public_reader(trial_case):
    case = trial_case
    draft = create(case)
    first = change(case, draft, operator="O1", key="trial-history-change-01")
    second = change(case, first["data"], key="trial-history-change-02")
    unchanged = change(case, second["data"], key="trial-history-change-03")
    assert first["data"]["change_history"][0]["validation"]["issues"]
    assert len(second["data"]["change_history"]) == 2
    assert unchanged["result"] == "unchanged"
    repo = WorkbenchCommandRepository(case.conn)
    for key, original, revision in (("trial-history-change-01", first, 2),
                                    ("trial-history-change-02", second, 3),
                                    ("trial-history-change-03", unchanged, 3)):
        stored = repo.get(key)
        assert stored is not None
        payload = json.loads(stored["outcome_json"])
        assert payload["data"]["change_history"] == {
            "format": HISTORY_REFERENCE_FORMAT, "draft_ref": draft["draft_ref"], "through_revision": revision}
        expected = dict(original, replayed=True)
        assert WorkbenchCommandService(case.conn).lookup(key) == expected
        assert service(case.conn).lookup(key) == expected
        # Old inline receipts retain the same complete public validation body.
        legacy = dict(stored, outcome_json=canonical_json({field: original[field] for field in ("result", "data", "warnings")}))
        assert repo.public_result(legacy, replayed=True) == expected
    assert change(case, draft, operator="O1", key="trial-history-change-01") == dict(first, replayed=True)

    client = api(case)
    generic = Blueprint("trial_generic_receipts", __name__)
    register_material_routes(generic)
    case.app.register_blueprint(generic)
    assert client.get("/api/workbench/v1/commands/trial-history-change-01").get_json() == dict(first, replayed=True)
    assert client.get("/api/workbench/v1/trial/commands/trial-history-change-01").get_json()["data"]["receipt"] == dict(first, replayed=True)

    # Permanent Changes and Receipts alone restore the result, even if the
    # original mutable workspace and its rows are no longer available.
    retained = sqlite3.connect(":memory:")
    retained.row_factory = sqlite3.Row
    try:
        for name in ("WorkbenchTrialChanges", "WorkbenchCommandReceipts"):
            declaration = case.conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()[0]
            retained.execute(declaration)
            rows = case.conn.execute('SELECT * FROM "' + name + '"').fetchall()
            retained.executemany('INSERT INTO "' + name + '" VALUES (' + ",".join("?" for _ in rows[0]) + ")", rows)
        retained.commit()
        assert WorkbenchCommandService(retained).lookup("trial-history-change-01") == dict(first, replayed=True)
        assert service(retained).lookup("trial-history-change-01") == dict(first, replayed=True)
        value = {"task_ref": draft["tasks"][0]["task_ref"], "machine_ref": case.ref("machine", "M2"),
                 "operator_ref": case.ref("operator", "O1"), "start": "2026-09-09T13:00:00"}
        assert service(retained).change(draft["draft_ref"], value, "expired-token", "trial-history-change-01") == dict(first, replayed=True)
    finally:
        retained.close()


def test_repeated_historical_validation_is_decoded_once_per_read(trial_case, monkeypatch):
    from data.repositories import workbench_trial_repo

    case = trial_case
    draft = create(case)
    first = change(case, draft)["data"]
    change(case, first, start="2026-09-10T08:00:00", key="trial-history-change-02")
    texts = [row[0] for row in case.conn.execute("SELECT validation_json FROM WorkbenchTrialChanges ORDER BY revision")]
    assert len(texts) == 2 and texts[0] == texts[1]
    decoded, original = Counter(), workbench_trial_repo.load_object

    def load_once(text):
        decoded[text] += 1
        return original(text)

    monkeypatch.setattr(workbench_trial_repo, "load_object", load_once)
    history = WorkbenchTrialRepository(case.conn).public_history(draft["draft_ref"])
    assert len(history) == 2 and history[0]["validation"] == original(texts[0])
    assert decoded[texts[0]] == 1
    WorkbenchTrialRepository(case.conn).public_history(draft["draft_ref"])
    assert decoded[texts[0]] == 2  # Request-local reuse never masks later reads.


def test_real_adoptions_batch_history_and_legacy_intent_reads(trial_case, monkeypatch):
    case = trial_case
    first_saved = saved_scenario(case)
    first = adoption_service(case.conn).adopt(first_saved["scenario_ref"], preview(case, first_saved),
        "trial-batch-history-adopt-01", INTENT)
    draft = create(case, {"base": {"plan_ref": first["data"]["official_plan"]["plan_ref"]}},
                   key="trial-batch-history-create-02")
    changed = change(case, draft, start="2026-09-09T14:00:00", key="trial-batch-history-change-02")["data"]
    second_saved = service(case.conn).save(changed["draft_ref"], {"name": "Second saved trial"},
        changed["write_context"]["write_token"], "trial-batch-history-save-02")["data"]
    second = adoption_service(case.conn).adopt(second_saved["scenario_ref"], preview(case, second_saved),
        "trial-batch-history-adopt-02", INTENT)
    versions = [result["data"]["official_plan"]["version"] for result in (first, second)]
    plan_refs = [result["data"]["official_plan"]["plan_ref"] for result in (first, second)]
    keys = ["trial-batch-history-adopt-01", "trial-batch-history-adopt-02"]
    # Legacy receipts omit input_json; recover both intents from their stored audits.
    case.conn.executemany("UPDATE WorkbenchCommandReceipts SET input_json=NULL WHERE request_key=?", [(key,) for key in keys])
    case.conn.commit()
    repo = WorkbenchCommandRepository(case.conn)
    receipts = []
    for key in keys:
        row = repo.get(key)
        assert row is not None
        receipts.append(row)
    statements, schema_checks = [], []
    check_schema = workbench_plan_identity_repo.workbench_plan_identity_contract_issues

    def schema_check(conn, *, structure):
        schema_checks.append(conn)
        return check_schema(conn, structure=structure)

    monkeypatch.setattr(workbench_plan_identity_repo, "workbench_plan_identity_contract_issues", schema_check)
    case.conn.set_trace_callback(statements.append)
    try:
        with TransactionManager(case.conn).transaction():
            context = PlanReadContext(case.conn)
            with context.read_scope():
                context.repo.prefetch_history_rows(versions)
                context.references.role_rows(versions)
                assert workbench_plan_identity_repo.WorkbenchPlanIdentityRepository(case.conn).read_revision() == context.references.read_revision()
                for version, plan_ref in zip(versions, plan_refs):
                    histories = context.history_rows(version)
                    assert len(histories) == 1 and histories[0]["version"] == version
                    identity = context.repo.get_history_identity_row(version)
                    assert identity is not None and identity["version"] == version
                    assert context.resolve(plan_ref).version == version
                    assert context.repo.list_plan_role_options(version) == context.references.read_role_options(version)
                inputs = repo.adoption_input_contents(receipts)
    finally:
        case.conn.set_trace_callback(None)
    histories = [sql.upper() for sql in statements if "FROM SCHEDULEHISTORY" in sql.upper() and "RESULT_SUMMARY" in sql.upper()]
    assert len(histories) == 2
    assert sum("VERSION IN (" in sql for sql in histories) == 1
    assert histories.count("SELECT RESULT_SUMMARY FROM SCHEDULEHISTORY") == 1
    role_queries = [sql.upper() for sql in statements if "FROM SCHEDULECANDIDATESELECTION S" in sql.upper()]
    assert len(role_queries) == 1 and "S.VERSION IN (" in role_queries[0]
    assert schema_checks == [case.conn]
    assert not any("PRAGMA_SCHEMA_VERSION" in sql.upper() for sql in statements)
    assert inputs == dict.fromkeys(keys, content_text(INTENT))

    statements.clear()
    case.conn.set_trace_callback(statements.append)
    try:
        history, _ = WorkbenchTrialAdoptionHistoryService(case.conn).read(first_saved["scenario_ref"])
    finally:
        case.conn.set_trace_callback(None)
    entry = history["items"][0]
    assert history["total_adoptions"] == 1
    assert entry["committed_plan"]["plan_ref"] == plan_refs[0]
    assert entry["current_state"] == "historical" and entry["adoption"]["reason"] == INTENT["reason"]
    assert not any(issue["code"].startswith("audit_") for issue in entry["evidence_gaps"])
    assert sum(sql.upper() == "SELECT RESULT_SUMMARY FROM SCHEDULEHISTORY" for sql in statements) == 1
    assert schema_checks == [case.conn, case.conn]
    assert adoption_service(case.conn).adopt(first_saved["scenario_ref"], "expired-token", keys[0], INTENT) == dict(first, replayed=True)


@pytest.mark.parametrize("raw", ['{"result":"committed","result":"committed"}', '{"version":NaN}', '{"version":1e999}',
                                 '{', '[]', None])
def test_stored_adoption_bodies_reject_duplicate_keys_nonfinite_numbers_and_non_objects(raw):
    # Receipt readers surface the rejection unchanged; the audit reader keeps it as an unproven-audit gap.
    with pytest.raises(WorkbenchCommandRejected) as error:
        json_object(raw)
    assert (error.value.code, error.value.status, str(error.value)) == (
        "adoption_history_invalid", 409, "采用记录里的试调方案、草稿和结果对不上，这里没有改动原记录。请刷新后重试。")
    audit, gaps = audit_fields({}, {}, {}, {}, {}, history={"result_summary": raw}, command_repo=None, adoption_inputs={})
    assert audit == dict.fromkeys(("reason", "declared_operator", "application_operator", "adopted_at"))
    assert gaps == [{"code": "audit_unproven", "message": "正式计划历史与保存结果对不上，经办人、原因和采用时间暂时不采信。"}]


def test_adoption_history_reader_keeps_its_outcomes_for_unreadable_stored_json(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    key = "trial-strict-json-adopt-01"
    version = adoption_service(case.conn).adopt(saved["scenario_ref"], preview(case, saved), key, INTENT)["data"]["official_plan"]["version"]
    summary = case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?", (version,)).fetchone()[0]
    reader = WorkbenchTrialAdoptionHistoryService(case.conn)
    for tail in (',"reason":"dup"}', ',"extra":NaN}', ',"extra":1e999}'):
        case.conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=?", (summary[:-1] + tail, version))
        case.conn.commit()
        entry = reader.read(saved["scenario_ref"])[0]["items"][0]
        assert [gap["code"] for gap in entry["evidence_gaps"] if gap["code"].startswith("audit_")] == ["audit_unproven"], tail
    case.conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=?", (summary, version))
    save_key = case.conn.execute("SELECT request_key FROM WorkbenchCommandReceipts WHERE action='trial.save'").fetchone()[0]
    for receipt_key in (save_key, key):
        outcome = case.conn.execute("SELECT outcome_json FROM WorkbenchCommandReceipts WHERE request_key=?", (receipt_key,)).fetchone()[0]
        for tail in (',"result":"committed"}', ',"extra":NaN}', ',"extra":1e999}'):
            case.conn.execute("UPDATE WorkbenchCommandReceipts SET outcome_json=? WHERE request_key=?", (outcome[:-1] + tail, receipt_key))
            case.conn.commit()
            with pytest.raises(WorkbenchCommandRejected) as error:
                reader.read(saved["scenario_ref"])
            assert (error.value.code, error.value.status, str(error.value)) == ("adoption_history_invalid", 409,
                "采用记录里的试调方案、草稿和结果对不上，这里没有改动原记录。请刷新后重试。"), (receipt_key, tail)
        case.conn.execute("UPDATE WorkbenchCommandReceipts SET outcome_json=? WHERE request_key=?", (outcome, receipt_key))
        case.conn.commit()

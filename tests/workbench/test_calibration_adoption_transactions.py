"""Actual SQLite rollback and competing adoption transactions."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core.models.workbench_calibration import MAX_SAMPLES
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.execution.production_report_void_dependencies import adopted_quota_impacts
from tests.workbench.calibration_adoption_support import INTENT, KEY, PREVIEW_INTENT, connect, service, snapshot, token
from tests.workbench.calibration_adoption_support import adoption_case as _adoption_case  # noqa: F401
from tests.workbench.calibration_adoption_support import ready_adoption_case as _ready_case  # noqa: F401
from tests.workbench.template_lineage_support import completed
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage_case  # noqa: F401


@pytest.mark.parametrize('table', ['WorkbenchCommandReceipts'])
def test_each_write_failure_rolls_back_quota_audit_and_receipt(ready_adoption_case, table):
    case = ready_adoption_case
    write_token = token(case)
    event = "UPDATE" if table == "PartOperations" else "INSERT"
    case.conn.execute("CREATE TRIGGER co_test_failure BEFORE " + event + " ON " + table +
                      " BEGIN SELECT RAISE(ABORT,'CO injected storage failure'); END")
    case.conn.commit()
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        service(case.conn).confirm(case.template_ref, write_token, KEY, INTENT)
    conn = connect(case)
    try:
        assert snapshot(conn) == before
        assert service(conn).receipt(case.template_ref, KEY) is None
    finally:
        conn.close()
    assert not case.conn.in_transaction
    case.conn.execute("DROP TRIGGER co_test_failure")
    result = service(case.conn).confirm(case.template_ref, write_token, KEY, INTENT)
    assert result["result"] == "committed" and not result["replayed"]


@pytest.mark.parametrize('same_key', [False])
def test_two_connections_recheck_the_same_preview_before_adoption(ready_adoption_case, same_key):
    case = ready_adoption_case
    write_token = token(case)
    barrier = Barrier(2)

    def worker(index):
        conn = connect(case)
        try:
            with case.app.app_context():
                barrier.wait(timeout=5)
                try:
                    return service(conn).confirm(case.template_ref, write_token,
                        KEY if same_key or index == 0 else KEY + "-other", INTENT)
                except WorkbenchCommandRejected as error:
                    return {"code": error.code}
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, (0, 1)))
    successes = [row for row in results if row.get("ok")]
    if same_key:
        assert len(successes) == 2
        assert sorted(row["replayed"] for row in successes) == [False, True]
        assert successes[0]["receipt_ref"] == successes[1]["receipt_ref"]
    else:
        assert len(successes) == 1
        assert [row for row in results if not row.get("ok")] == [{"code": "stale_write"}]
    assert case.conn.execute("SELECT count(*) FROM WorkbenchCalibrationAdoptions").fetchone()[0] == 1
    assert case.conn.execute("SELECT count(*) FROM WorkbenchCommandReceipts WHERE action='calibration.adopt'").fetchone()[0] == 1


def test_report_revision_change_rejects_preview_with_the_same_recommendation(ready_adoption_case):
    case = ready_adoption_case
    _, extra_reports = completed(case, [3] * (MAX_SAMPLES + 1), prefix="OLDER-SAMPLE", version=3)
    before = service(case.conn).preview(case.template_ref, PREVIEW_INTENT)
    selected_reports = {ref for sample in before["samples"] for ref in sample["report_refs"]}
    unselected = next(row for row in extra_reports if row["report_ref"] not in selected_reports)
    original = case.report_projection(unselected["report_ref"])
    case.command("correct", original.report_ref,
                 {"remark": "Checked the original record", "original_revision_ref": original.revision_ref,
                  "reason": "Corrected the record note", "declared_operator": "Reviewer"})
    after = service(case.conn).preview(case.template_ref, PREVIEW_INTENT)
    assert after["validation"]["can_adopt"]
    assert after["suggestion"] == before["suggestion"]
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        service(case.conn).confirm(case.template_ref, before["write_context"]["write_token"], KEY, INTENT)
    assert rejected.value.code == "stale_write"
    assert case.conn.execute("SELECT count(*) FROM WorkbenchCalibrationAdoptions").fetchone()[0] == 0


def test_adoption_keeps_raw_reports_once_and_binds_source_versions(ready_adoption_case):
    case = ready_adoption_case
    result = service(case.conn).confirm(case.template_ref, token(case), KEY, INTENT)
    archived = case.conn.execute("SELECT evidence_json FROM WorkbenchCalibrationAdoptions").fetchone()[0]
    evidence = json.loads(archived)
    binding = evidence["snapshot"]
    assert binding["schema_version"] == 2 and "facts_fingerprint" not in binding
    assert binding["lineage_available"] and isinstance(binding["source_constraints"], list)
    assert json.loads(binding["suggestion"]["template_snapshot"]) == {
        "source_ref": case.template_ref, "revision": result["data"]["template_revision_before"]}
    assert len(binding["source_revisions"]) >= len(evidence["samples"])
    for sample in evidence["samples"]:
        revision = json.loads(sample["sample_revision"])
        assert revision["source_ref"] == sample["sample_ref"]
        assert revision["report_revision_refs"] == sample["report_revision_refs"]
        assert revision["lineage"]["evidence_ref"] == sample["lineage_evidence_ref"]
        assert revision["lineage"]["birth_event_id"] in revision["lineage"]["event_ids"]
        assert not {"reports", "execution", "instance_snapshot", "instance_fingerprint"}.intersection(revision)
        assert "reports" not in revision["lineage"]
        assert len(sample["reports"]) == 1
    assert all(set(row) == {"sample_ref", "sample_revision", "eligible", "exclusion_reasons"}
               for row in binding["source_revisions"])
    sample = evidence["samples"][0]
    impacts = adopted_quota_impacts(case.conn, sample["report_refs"][0], sample["sample_ref"])
    assert [row["adoption_ref"] for row in impacts] == [result["data"]["adoption_ref"]]


def test_stale_calibration_snapshot_after_later_report_returns_409_not_500(ready_adoption_case):
    from datetime import datetime

    from flask import Blueprint, g

    from web.routes.workbench.calibration import register_calibration_routes

    case = ready_adoption_case
    bp = Blueprint("calibration_stale_snapshot_test", __name__)
    register_calibration_routes(bp)
    case.app.register_blueprint(bp)

    @case.app.before_request
    def _bind_db():
        g.db = case.conn

    client = case.app.test_client()
    initial = client.get("/api/workbench/v1/calibration")
    assert initial.status_code == 200, initial.get_json()
    snapshot_ref = initial.get_json()["meta"]["snapshot_ref"]
    case.now = datetime(2099, 1, 1, 12, 0, 0)
    completed(case, [4], prefix="LATER-REPORT", version=3)
    stale = client.get("/api/workbench/v1/calibration", query_string={"snapshot_ref": snapshot_ref})
    assert stale.status_code == 409, stale.get_json()
    assert stale.get_json()["error"]["code"] == "snapshot_stale"

"""Actual current-schema source qualification, frozen adoption and withdrawal limits."""

from contextlib import closing

import pytest

from core.infrastructure.database import get_connection
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.part_service import PartService
from core.services.workbench.template_lineage import TemplateLineageWriter
from tests.workbench.execution_ledger_support import LedgerCase
from tests.workbench.final_execution_cases import ADOPT_TABLES, CALIBRATION, command, seed, sql
from tests.workbench.final_execution_cases import final_calibration_host as final_calibration_host
from tests.workbench.final_execution_cases import final_e_runtime as final_e_runtime
from tests.workbench.final_execution_support import changes, old_rows_preserved, restart_preserved
from tests.workbench.live_environment import write_json

INTENT = {"reason": "逐项核对真实整道完工样本", "declared_operator": "最终验收员"}


def preview(host):
    return host.json(CALIBRATION + "/" + seed(host)["template_ref"] + "/adopt-preview", body={"input": INTENT})["data"]


def detail(host):
    reading = host.json(CALIBRATION)
    return host.json(CALIBRATION + "/" + seed(host)["template_ref"],
                     query={"snapshot_ref": reading["meta"]["snapshot_ref"]})["data"]


def test_median_preview_cancel_atomic_adoption_lock_receipt_and_real_restart(final_calibration_host):
    host = final_calibration_host
    original = host.state()
    data = detail(host)
    selected = [row for row in data["samples"] if row["selected"]]
    assert sorted(row["unit_hours"] for row in selected) == [1, 2, 3, 4, 50]
    assert all(row["eligible"] and row["lineage_evidence_ref"] for row in selected)
    assert data["suggestion"]["sample_count"] == 5 and data["suggestion"]["suggested_unit_hours"] == 3
    inspected = preview(host)
    assert inspected["validation"]["can_adopt"] and host.state() == original
    # Closing a preview without a confirm leaves every database table unchanged.
    assert preview(host)["suggestion"]["suggested_unit_hours"] == 3 and host.state() == original
    body = command(inspected["write_context"], {**INTENT, "confirm": True})
    path = CALIBRATION + "/" + seed(host)["template_ref"] + "/adopt"
    sql(host, "CREATE TRIGGER final_e_adopt_failure BEFORE INSERT ON WorkbenchCommandReceipts "
              "BEGIN SELECT RAISE(ABORT,'final-e-adopt-receipt-failure'); END")
    failed = host.json(path, body=body, status=500)
    assert failed["committed"] == "unknown" and host.state() == original
    sql(host, "DROP TRIGGER final_e_adopt_failure")
    receipt = host.json(path, body=body)
    after = host.state()
    assert changes(original, after) == ADOPT_TABLES
    old_rows_preserved(original, after, {"PartOperations", "WorkbenchEntityRefs"})
    assert receipt["data"]["locked"] is True and receipt["data"]["new_unit_hours"] == 3
    assert receipt["data"]["effect_scope"] == "future_template_use_only"
    with closing(get_connection(str(host.root / "db/aps-live.db"))) as conn:
        with pytest.raises(WorkbenchCommandRejected) as error:
            PartService(conn).update_internal_hours("P1", 1, 0, 99)
        assert error.value.code == "calibration_quota_locked"
    assert host.state() == after
    host.stop()
    host.start(reuse=True)
    restarted_state = host.state()
    restart_audit = restart_preserved(after, restarted_state)
    replay = host.json(path, body={**body, "write_token": "expired-on-process-restart"})
    assert replay["replayed"] and replay["receipt_ref"] == receipt["receipt_ref"]
    assert replay["data"] == receipt["data"]
    assert host.json(path + "/receipts/" + body["request_key"]) == replay
    assert not preview(host)["validation"]["can_adopt"]
    assert host.state() == restarted_state
    write_json(host.root / "calibration-proof.json", {"detail_before": data, "preview": inspected,
        "failed_atomic_confirm": failed, "receipt": receipt, "replay": replay,
        "strict_changed_tables": sorted(ADOPT_TABLES), "old_rows_preserved": True, "real_restart": True,
        "restart_audit": restart_audit})


@pytest.mark.parametrize("kind,code", [("pause", "pause_contamination"), ("exception", "known_exception"),
                                      ("withdraw", "template_lineage_withdrawn")])
def test_real_original_pause_exception_and_withdrawal_exclude_without_erasing_reports(final_calibration_host, kind, code):
    host = final_calibration_host
    old = host.state()
    original_preview = preview(host)
    op = seed(host)["sample_operation_ids"][0]
    with closing(get_connection(str(host.root / "db/aps-live.db"))) as conn:
        case = LedgerCase(conn)
        if kind == "withdraw":
            ref = case.ledger.repo.task(case.task(1, op))["operation_ref"]
            with TransactionManager(conn).transaction():
                assert TemplateLineageWriter(conn).withdraw(ref, "核对后撤销错误来源关联")
                assert not TemplateLineageWriter(conn).withdraw(ref, "核对后撤销错误来源关联")
        else:
            batch = conn.execute("SELECT batch_id FROM BatchOperations WHERE id=?", (op,)).fetchone()[0]
            case.event(op, "start", batch_id=batch, time="2026-09-09T08:00:00")
            case.event(op, kind, batch_id=batch, time="2026-09-09T08:30:00")
    after_event = host.state()
    for table in ("WorkbenchProductionReports", "WorkbenchProductionReportRevisions", "Schedule", "ScheduleHistory"):
        assert after_event[table] == old[table], table
    current = detail(host)
    assert current["suggestion"]["sample_count"] == 4
    assert current["suggestion"]["suggested_unit_hours"] is None
    reasons = {reason["code"] for row in current["samples"] for reason in row["exclusion_reasons"]}
    assert code in reasons, reasons
    assert not preview(host)["validation"]["can_adopt"]
    stale_body = command(original_preview["write_context"], {**INTENT, "confirm": True})
    stale = host.json(CALIBRATION + "/" + seed(host)["template_ref"] + "/adopt", body=stale_body, status=409)
    assert stale["error"]["code"] == "stale_write" and stale["committed"] is False
    assert host.state() == after_event
    write_json(host.root / ("qualification-" + kind + ".json"), {"current": current, "stale": stale,
        "old_reports_and_plans_identical": True, "changed_tables": sorted(changes(old, after_event))})

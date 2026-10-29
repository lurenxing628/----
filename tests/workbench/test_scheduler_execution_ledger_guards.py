"""真实执行事实经当前 worker 与采用路径保持不变。"""

import json

from core.services.scheduler.execution.execution_ledger_guard import ensure_ledger_execution_schedulable
from core.services.workbench.run.preflight import PreflightService
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.field_workspace_support import FieldAPI
from tests.workbench.run_candidate_adoption_support import INTENT, preview, service
from tests.workbench.run_candidate_support import candidate_case as candidate_fixture  # noqa: F401
from tests.workbench.run_candidate_support import compute
from tests.workbench.scheduler_execution_ledger_support import formal_rows, read_facts


def test_incomplete_report_can_be_supplemented_and_used_by_real_replan(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    adopted = service(case.conn).adopt(refs[0], preview(case, refs[0]), "first-adoption-001", INTENT)
    version = adopted["data"]["official_plan"]["version"]
    api = FieldAPI(case)
    api.create({"actual_start": "2026-09-09T08:00:00", "actual_end": "2026-09-09T10:00:00",
                "actual_machine_ref": case.ref("machine", "M1"),
                "actual_operator_ref": case.ref("operator", "O1")}, api.task())
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    blockers = PreflightService(case.conn).evaluate(case.settings("B1", "B2"))[0]["blockers"]
    assert [row["code"] for row in blockers] == ["execution_review_required"]
    original = formal_rows(case.conn)["Schedule"]
    record = api.task()["execution"]["reports"][0]
    case.command("supplement", record["report_ref"], {
        "original_revision_ref": record["revision_ref"],
        "reason": "保留原实际，补齐完工数量与有效工时",
        "completed_quantity": 3,
        "effective_processing_hours": 1.5,
    })
    assert api.task()["execution"]["data_quality"] == "complete"
    ensure_ledger_execution_schedulable(read_facts(case.conn, version))
    accepted = case.accept(key="supplement-replan-001", settings=case.settings("B1", "B2"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete" and result["candidates"]
    tasks = [json.loads(row[0]) for row in case.conn.execute(
        "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?",
        (result["candidates"][0]["candidate_ref"],))]
    actual = next(row for row in tasks if row["op_id"] == case.op_id)
    assert (actual["start_time"], actual["end_time"]) == ("2026-09-09T08:00:00", "2026-09-09T10:00:00")
    assert formal_rows(case.conn)["Schedule"] == original

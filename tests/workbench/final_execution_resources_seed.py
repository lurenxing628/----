"""Real report corrections create nine resource groups before the preservation baseline."""

from tests.workbench.execution_ledger_support import LedgerCase
from tests.workbench.reports_review_browser_seed import seed as report_seed


def resource_groups(api):
    result = report_seed(api)
    with api.db() as conn:
        case = LedgerCase(conn)
        originals = case.ledger.get_task(case.task(1, 1)).reports[:7]
        changes = []
        for index, report in enumerate(originals):
            machine, operator = "GROUP-M" + str(index), "GROUP-O" + str(index)
            conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'T1')", (machine, "实报设备组 " + str(index + 1)))
            conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", (operator, "实报人员组 " + str(index + 1)))
            conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", (operator, machine))
            conn.commit()
            receipt = case.command("correct", report.report_ref, {"original_revision_ref": report.revision_ref,
                "reason": "私有验收样本的实际资源记录核对", "actual_machine_ref": case.ref("machine", machine),
                "actual_operator_ref": case.ref("operator", operator)}, key="final-e-resource-group-" + str(index))
            changes.append({"report_ref": report.report_ref, "receipt_ref": receipt["receipt_ref"], "machine_ref": case.ref("machine", machine), "operator_ref": case.ref("operator", operator)})
        result.update(plan_ref=case.plan_ref(1), resource_groups_expected=9, resource_corrections=changes,
                      seeded_before_preservation_baseline=True)
    return result

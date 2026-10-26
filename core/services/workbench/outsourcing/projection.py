"""Public facts keep receipt confirmation separate from production reporting."""

from typing import NoReturn

from core.models.workbench_outsourcing import STATES
from core.shared.strict_json import load_strict_json


def _corrupt_fact() -> NoReturn:
    raise ValueError("已保存的外协确认事实无法读取。")


def values(row):
    return {"sent": row["sent"], "planned": row["planned"], "returned": row["returned"], "confirmedState": row["confirmed_state"]}


def fact(row):
    before = load_strict_json(row["before_json"], on_malformed=_corrupt_fact)
    return {"fact_ref": row["fact_ref"], "before": before, "after": values(row),
            "declared_operator": row["declared_operator"], "local_operator": row["local_operator"],
            "reason": row["reason"], "confirmed_at": row["recorded_at"], "previous_fact_ref": row["previous_fact_ref"]}


def execution_boundary(target):
    return {"automatically_reported": False, "operation_refs": target["operation_refs"],
            "service": "WorkbenchProductionReportService", "lookup_target": "/api/workbench/v1/execution/tasks",
            "lookup_parameter": "operation_ref",
            "command_target_template": "/api/workbench/v1/execution/tasks/<task_ref>/reports",
            "requires": ["current_official_task_ref", "execution_write_context", "explicit_actual_values", "separate_request_key"],
            "reason": "工序完工后，请到「现场记录」登记完成数量与有效工时。"}


def receipt(header, latest, now, *, source_state, issues):
    current = values(latest)
    return {"outsourcing_ref": header["outsourcing_ref"], "target": header["origin"], **current,
            "state_label": STATES[current["confirmedState"]], "confirmed_at": latest["recorded_at"],
            "declared_operator": latest["declared_operator"], "local_operator": latest["local_operator"],
            "reason": latest["reason"], "latest_fact_ref": latest["fact_ref"], "history_count": latest["sequence"],
            "awaiting_return": current["returned"] is None,
            "overdue": current["returned"] is None and current["planned"] < now.isoformat(timespec="seconds"),
            "tracking_basis": "manual_receipt_facts", "source_state": source_state, "issues": issues,
            "execution": execution_boundary(header["target"])}

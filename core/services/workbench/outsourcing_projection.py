"""Public facts keep receipt confirmation separate from production reporting."""

import json

from core.models.workbench_outsourcing import STATES


def values(row):
    return {"sent": row["sent"], "planned": row["planned"], "returned": row["returned"], "confirmedState": row["confirmed_state"]}


def fact(row):
    return {"fact_ref": row["fact_ref"], "before": json.loads(row["before_json"]), "after": values(row),
            "declared_operator": row["declared_operator"], "local_operator": row["local_operator"],
            "reason": row["reason"], "confirmed_at": row["recorded_at"], "previous_fact_ref": row["previous_fact_ref"]}


def execution_boundary(target):
    return {"automatically_reported": False, "operation_refs": target["operation_refs"],
            "service": "WorkbenchProductionReportService", "lookup_target": "/api/workbench/v1/execution/tasks",
            "lookup_parameter": "operation_ref",
            "command_target_template": "/api/workbench/v1/execution/tasks/<task_ref>/reports",
            "requires": ["current_official_task_ref", "execution_write_context", "explicit_actual_values", "separate_request_key"],
            "reason": "回厂只确认外协物流事实，不推定工序完工、产量、有效工时或当前正式任务。"}


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

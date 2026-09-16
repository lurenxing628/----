"""Business preflight, not a schedule, publication or worker admission."""

from collections import defaultdict

from core.models.workbench_preflight import issue, normalize_preflight_input
from core.services.workbench.preflight_checks import PreflightChecks, stored_date
from core.services.workbench.preflight_dependencies import link_predecessors
from core.services.workbench.preflight_execution import execution_projections, is_protected
from core.services.workbench.preflight_facts import PreflightFacts
from core.services.workbench.preflight_result import summarize


def task_row(facts, batch, op, projection):
    execution_keys = ("execution_state", "completion_basis", "first_actual_start", "confirmed_finish",
                      "remaining_quantity", "data_quality", "known_completed_quantity", "unknown_record_count")
    return {"operation_ref": facts.operation_ref(op), "batch_ref": batch["ref"], "batch_id": batch["batch_id"],
            "sequence": op["seq"], "piece_id": op["piece_id"], "label": op["op_type_name"], "source": op["source"],
            "status": "eligible", "issues": [], "predecessor_refs": [],
            "has_execution_facts": bool(projection.get("reports") or projection.get("legacy_facts")),
            "execution": {key: projection.get(key) for key in execution_keys}}


def operation_gaps(checks, batch, op, projection):
    gaps = checks.fields(batch, op)
    if projection["data_quality"] == "invalid":
        gaps.extend(projection["data_gaps"])
    if batch["ready_date"] is not None and stored_date(batch["ready_date"]) is None:
        gaps.append(issue("ready_date_invalid", "批次的齐套日期格式不对。请到批次管理改正。"))
    if batch["status"] not in ("pending", "scheduled", "processing", "completed", "cancelled"):
        gaps.append(issue("batch_status_invalid", "批次状态无效，请到批次管理核对。"))
    if op["status"] not in ("pending", "scheduled"):
        gaps.append(issue("operation_status_invalid", "工序状态无效，请到批次管理核对。"))
    return gaps


def classify(checks, batch, op, projection, settings, ready_reasons):
    if is_protected(projection, op):
        reasons = [issue("actuals_preserved", "这道工序已有报工记录或已经开工，原记录保留，整道工序不重排。")]
        reasons.extend(projection["data_gaps"])
        if projection["execution_state"] != "complete":
            reasons.append(issue("remaining_execution_unresolved", "这道工序已经开工；剩下的数量要先在现场记录里确认，暂时不能重排。"))
        return "protected", reasons
    gaps = operation_gaps(checks, batch, op, projection)
    if gaps:
        return "blocked", gaps + checks.resources(op)
    if batch["status"] in ("completed", "cancelled"):
        return "skipped", [issue("batch_closed", "批次已完成或取消，不进入本次排产。")]
    if batch["quantity"] == 0 and op["source"] != "internal":
        return "skipped", [issue("zero_quantity", "批次数量填的是 0，没有要排的量。")]
    if ready_reasons:
        return "skipped", ready_reasons
    ready_date = stored_date(batch["ready_date"])
    if ready_date and ready_date > settings["end_date"]:
        return "skipped", [issue("ready_after_window", "齐套日期晚于这次排产日期范围，排不进来。请放宽日期范围，或到批次管理调齐套日期。")]
    missing = checks.resources(op)
    if missing:
        return ("auto_assign_required" if settings["missing_resource_policy"] == "auto_assign" else "skipped"), missing
    return "eligible", []


class PreflightService:
    def __init__(self, conn):
        self.facts = PreflightFacts(conn)

    def evaluate(self, value):
        settings = normalize_preflight_input(value)
        with self.facts.snapshot() as fingerprint:
            batches = self.facts.selected(settings["batch_refs"])
            selected_ids = {row["batch_id"] for row in batches}
            operations = [row for row in self.facts.tables["BatchOperations"] if row["batch_id"] in selected_ids]
            projections, ledger_reasons = execution_projections(self.facts, operations)
            checks = PreflightChecks(self.facts.tables)
            grouped = defaultdict(list)
            for op in operations:
                grouped[op["batch_id"]].append(op)
            rows, no_route, unready = [], [], []
            for batch in batches:
                ops = grouped[batch["batch_id"]]
                if not ops:
                    no_route.append(batch)
                ready_reasons = checks.readiness(batch, settings["ready_check"])
                if checks.readiness(batch, True):
                    unready.append({"batch_ref": batch["ref"], "batch_id": batch["batch_id"]})
                batch_rows = []
                for op in ops:
                    projection = projections[self.facts.operation_ref(op)]
                    row = task_row(self.facts, batch, op, projection)
                    row["status"], row["issues"] = classify(checks, batch, op, projection, settings, ready_reasons)
                    batch_rows.append(row)
                link_predecessors(batch_rows)
                rows.extend(batch_rows)
            return summarize(settings, batches, rows, no_route, unready, ledger_reasons), fingerprint

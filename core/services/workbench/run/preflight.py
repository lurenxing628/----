"""Business preflight, not a schedule, publication or worker admission."""

from collections import defaultdict
from types import SimpleNamespace

from core.errors import AppError
from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_preflight import issue, normalize_preflight_input
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.facts.piece_scope import build_piece_adoption_scope
from core.services.workbench.facts.preflight_checks import PreflightChecks, stored_date
from core.services.workbench.facts.preflight_dependencies import link_predecessors, piece_scope_problem

from .input_config import hold_window
from .input_external import external_resource_issues, preflight_external_cycles
from .preflight_execution import execution_projections, is_protected
from .preflight_facts import PreflightFacts
from .preflight_held import held_arrangement_reasons
from .preflight_result import summarize


def task_row(facts, batch, op, projection):
    execution_keys = ("execution_state", "completion_basis", "first_actual_start", "confirmed_finish",
                      "remaining_quantity", "data_quality", "known_completed_quantity", "unknown_record_count")
    return {"operation_ref": facts.operation_ref(op), "op_id": op["id"], "batch_ref": batch["ref"], "batch_id": batch["batch_id"],
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


def _classification_gaps(checks, batch, op, projection, external_cycle):
    if external_cycle is None:
        return operation_gaps(checks, batch, op, projection)
    gaps = checks.protected_resources(op)
    if projection["data_quality"] == "invalid":
        gaps.extend(projection["data_gaps"] or [issue("execution_invalid", "同组工序的报工记录无法核对，请检查现场记录。")])
    return gaps


def classify(checks, batch, op, projection, settings, ready_reasons, *, external_cycle=None):
    if is_protected(projection, op):
        reasons = [issue("actuals_preserved", "这道工序已有报工记录或已经开工，原记录保留，整道工序不重排。")]
        reasons.extend(projection["data_gaps"])
        if projection["execution_state"] != "complete":
            reasons.append(issue("remaining_execution_unresolved", "这道工序已经开工；剩下的数量要先在现场记录里确认，暂时不能重排。"))
        return "protected", reasons
    gaps = _classification_gaps(checks, batch, op, projection, external_cycle)
    if gaps:
        return "blocked", gaps + checks.resources(op)
    if external_cycle is not None:
        return "protected", [issue("external_group_actuals_preserved", "合并外协组已有实际记录，整组保留同一固定周期。")]
    if batch["status"] in ("completed", "cancelled"):
        return "skipped", [issue("batch_closed", "批次已完成或取消，不进入本次排产。")]
    if batch["quantity"] == 0 and op["source"] != "internal":
        return "skipped", [issue("zero_quantity", "批次数量填的是 0，没有要排的量。")]
    if ready_reasons:
        return "skipped", ready_reasons
    ready_date = stored_date(batch["ready_date"])
    if settings["ready_check"] and ready_date and ready_date > settings["end_date"]:
        return "skipped", [issue("ready_after_window", "齐套日期晚于这次排产日期范围，排不进来。请放宽日期范围，或到批次管理调齐套日期。")]
    missing = checks.resources(op)
    if missing:
        return ("auto_assign_required" if settings["missing_resource_policy"] == "auto_assign" else "skipped"), missing
    return "eligible", []


def batch_dependencies(batch, operations, rows, settings):
    if not any(op["piece_id"] is not None for op in operations):
        link_predecessors(rows)
        return []
    try:
        scope = build_piece_adoption_scope([SimpleNamespace(**op) for op in operations],
            {batch["batch_id"]: SimpleNamespace(quantity=batch["quantity"])})
    except PieceAdoptionBlocked as exc:
        problem = issue(exc.code, str(exc), batch_ref=batch["ref"])
        for row in rows:
            if row["status"] != "protected":
                row["status"] = "blocked"
            row["issues"].append(problem)
        return [problem]
    link_predecessors(rows, piece_scope=scope)
    problem = piece_scope_problem(rows, settings)
    return [dict(problem, batch_ref=batch["ref"])] if problem else []


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
            cycles, arrangement_reasons = self._external_cycles(batches, operations, projections)
            checks = PreflightChecks(self.facts.tables)
            grouped = defaultdict(list)
            for op in operations:
                grouped[op["batch_id"]].append(op)
            rows, no_route, unready, dependency_reasons = [], [], [], []
            for batch in batches:
                ops = grouped[batch["batch_id"]]
                if not ops:
                    no_route.append(batch)
                if checks.readiness(batch, True):
                    unready.append({"batch_ref": batch["ref"], "batch_id": batch["batch_id"]})
                batch_rows = []
                for op in ops:
                    projection = projections[self.facts.operation_ref(op)]
                    row = task_row(self.facts, batch, op, projection)
                    op_ready, release_day = ([], None) if op["id"] in cycles else checks.operation_readiness(batch, op, settings)
                    row["material_ready_date"] = release_day if release_day != "1900-01-01" else None
                    row["status"], row["issues"] = classify(checks, batch, op, projection, settings, op_ready,
                                                          external_cycle=cycles.get(op["id"]))
                    if op["id"] in cycles:
                        row["external_execution_cycle"] = cycles[op["id"]]
                    batch_rows.append(row)
                dependency_reasons.extend(batch_dependencies(batch, ops, batch_rows, settings))
                rows.extend(batch_rows)
            held, notes, marks = self._arrangement_reasons(settings, batches, operations, rows, projections, ledger_reasons,
                                                           checks, cycles)
            for row in rows:
                row["held"] = marks.get(row["op_id"])
            return summarize(settings, batches, rows, no_route, unready, ledger_reasons,
                             dependency_reasons + arrangement_reasons + held, notes,
                             hold=hold_window(self.facts.conn, settings)), fingerprint

    def _external_cycles(self, batches, operations, projections):
        try:
            return preflight_external_cycles(self.facts, batches, operations, projections)
        except (AppError, ValueError, TypeError, KeyError, OverflowError):
            # 周期核对不了是这次排产的阻断，不是报工台账没开通；具体原因（如外协报工带本厂资源）另行列出。
            return {}, [issue("external_execution_cycle_unproven", "合并外协组的实际周期无法核对，请检查现场记录和原安排后重新检查。")]

    def _arrangement_reasons(self, settings, batches, operations, rows, projections, ledger_reasons, checks, cycles):
        """排产计算或采用才会发现、却在开始前就能看出的冲突：外协记录占了本厂资源，
        锁定或不重排时段保留的原安排按现在的资料已不成立。返回 (阻断原因, 提醒, {工序: 保留标记})。"""
        svc = ScheduleService(self.facts.conn)
        version = svc.history_repo.get_latest_version()
        ledger_ready = not any(item["code"] == "execution_ledger_unavailable" for item in ledger_reasons)
        reasons = external_resource_issues(self.facts, svc, operations, projections, version) if ledger_ready else []
        # 与排产计算查锁定和冻结的范围一致：这次要重排的工序，加上合并外协组按实际周期派生保留的成员。
        held_ids = {row["op_id"] for row in rows if row["status"] in ("eligible", "auto_assign_required")} | set(cycles)
        held, notes, marks = held_arrangement_reasons(self.facts, svc, checks, settings, version, batches, operations,
                                                      held_ids, cycles, projections)
        return reasons + held, notes, marks

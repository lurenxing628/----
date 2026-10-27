"""Business preflight, not a schedule, publication or worker admission."""

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, cast

from core.errors import AppError, ValidationError
from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_preflight import issue, normalize_preflight_input
from core.services.workbench.facts.piece_scope import build_piece_adoption_scope
from core.services.workbench.facts.preflight_checks import stored_date
from core.services.workbench.facts.preflight_dependencies import link_predecessors
from core.services.workbench.facts.run_input_rows import OPERATION_STATES, mutable_classification
from core.services.workbench.facts.stored_algo_inputs import stored_batch_operation

from .input_config import hold_window, run_options
from .input_external import external_resource_issues, preflight_external_cycles
from .preflight_execution import execution_projections, is_protected
from .preflight_facts import PreflightFacts
from .preflight_held import held_arrangement_reasons
from .preflight_result import summarize

if TYPE_CHECKING:
    from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot
    from core.services.workbench.facts.production_capture import ProductionFactsCapture


@dataclass
class PreparedPreflight:
    data: dict
    fingerprint: str
    settings: dict
    capture: object
    preflight_facts: PreflightFacts
    config_snapshot: Optional["ScheduleConfigSnapshot"]
    execution_projections: list
    baseline: object = None
    prepared_input: object = None
    config_error: Optional[ValidationError] = None
    run_options: object = None
    held_arrangements: object = None


def task_row(operation_ref, batch, op, projection):
    execution_keys = ("execution_state", "completion_basis", "first_actual_start", "confirmed_finish",
                      "remaining_quantity", "data_quality", "known_completed_quantity", "unknown_record_count")
    return {"operation_ref": operation_ref, "op_id": op["id"], "batch_ref": batch["ref"], "batch_id": batch["batch_id"],
            "sequence": op["seq"], "piece_id": op["piece_id"], "label": op["op_type_name"], "source": op["source"],
            "status": "eligible", "issues": [], "predecessor_refs": [],
            "has_execution_facts": bool(projection["reports"] or projection["legacy_facts"]),
            "execution": {key: projection[key] for key in execution_keys}}


def operation_gaps(checks, batch, op, projection):
    gaps = checks.fields(batch, op)
    if projection["data_quality"] == "invalid":
        gaps.extend(projection["data_gaps"])
    if batch["ready_date"] is not None and stored_date(batch["ready_date"]) is None:
        gaps.append(issue("ready_date_invalid", "批次的齐套日期格式不对。请到批次管理改正。"))
    if batch["status"] not in ("pending", "scheduled", "processing", "completed", "cancelled"):
        gaps.append(issue("batch_status_invalid", "批次状态无效，请到批次管理核对。"))
    if op["status"] not in OPERATION_STATES:
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
    return mutable_classification(checks, batch, op, settings, ready_reasons)


def batch_dependencies(batch, operations, rows):
    if not any(op["piece_id"] is not None for op in operations):
        link_predecessors(rows)
        return []
    try:
        scope = build_piece_adoption_scope([stored_batch_operation(op) for op in operations],
            {batch["batch_id"]: batch["quantity"]})
    except PieceAdoptionBlocked as exc:
        problem = issue(exc.code, str(exc), batch_ref=batch["ref"])
        for row in rows:
            if row["status"] != "protected":
                row["status"] = "blocked"
            row["issues"].append(problem)
        return [problem]
    link_predecessors(rows, piece_scope=scope)
    return []


class PreflightService:
    def __init__(self, conn, *, facts=None):
        self._provided_facts = facts
        self.facts = facts if facts is not None else PreflightFacts(conn)

    def evaluate(self, value):
        prepared = self.evaluate_prepared(value)
        return prepared.data, prepared.fingerprint

    def evaluate_prepared(self, value) -> PreparedPreflight:
        settings = normalize_preflight_input(value)
        self.facts = self._provided_facts if self._provided_facts is not None else PreflightFacts(self.facts.conn)
        with self.facts.snapshot() as fingerprint:
            config, config_error = None, None
            try:
                config = self.facts.configuration()
            except ValidationError as exc:
                config_error = exc
            options = run_options(settings, config) if config is not None else None
            if options is not None:
                settings = {**settings, "time_budget_seconds": options["time_budget_seconds"]}
            batches = self.facts.selected(settings["batch_refs"])
            selected_ids = {row["batch_id"] for row in batches}
            operations = [row for row in self.facts.tables["BatchOperations"] if row["batch_id"] in selected_ids]
            prepared_projections = []
            projections = execution_projections(self.facts, operations, prepared=prepared_projections)
            cycles, arrangement_reasons = self._external_cycles(batches, operations, projections)
            checks = self.facts.checks()
            grouped = defaultdict(list)
            for op in operations:
                grouped[op["batch_id"]].append(op)
            rows, no_route, unready, dependency_reasons = [], [], [], []
            for batch in batches:
                ops = grouped[batch["batch_id"]]
                if not ops:
                    no_route.append(batch)
                if checks.readiness(batch):
                    unready.append({"batch_ref": batch["ref"], "batch_id": batch["batch_id"]})
                batch_rows = []
                for op in ops:
                    operation_ref = self.facts.operation_ref(op)
                    projection = projections[operation_ref]
                    row = task_row(operation_ref, batch, op, projection)
                    op_ready, release_day = ([], None) if op["id"] in cycles else checks.operation_readiness(batch, op, settings)
                    row["material_ready_date"] = release_day if release_day != "1900-01-01" else None
                    row["status"], row["issues"] = classify(checks, batch, op, projection, settings, op_ready,
                                                          external_cycle=cycles.get(op["id"]))
                    if op["id"] in cycles:
                        row["external_execution_cycle"] = cycles[op["id"]]
                    batch_rows.append(row)
                dependency_reasons.extend(batch_dependencies(batch, ops, batch_rows))
                rows.extend(batch_rows)
            hold = (None, "default") if config_error is not None else hold_window(settings, snapshot=config)
            held, notes, marks, held_obj = self._arrangement_reasons(
                settings, batches, operations, rows, projections,
                checks, cycles, hold_window_bounds=hold[0],
            )
            for row in rows:
                row["held"] = marks.get(row["op_id"])
            data = summarize(settings, batches, rows, no_route, unready,
                             dependency_reasons + arrangement_reasons + held, notes,
                             hold=hold)
            data["run_options"] = options
            return PreparedPreflight(
                data, fingerprint, settings, self.facts.capture, self.facts,
                config, prepared_projections, config_error=config_error, run_options=options,
                held_arrangements=held_obj,
            )

    def _external_cycles(self, batches, operations, projections):
        try:
            return preflight_external_cycles(self.facts, batches, operations, projections)
        except AppError:
            # 周期核对不了是这次排产的阻断，不是报工台账没开通；具体原因（如外协报工带本厂资源）另行列出。
            return {}, [issue("external_execution_cycle_unproven", "合并外协组的实际周期无法核对，请检查现场记录和原安排后重新检查。")]

    def _arrangement_reasons(self, settings, batches, operations, rows, projections, checks, cycles,
                             *, hold_window_bounds):
        """排产计算或采用才会发现、却在开始前就能看出的冲突：外协记录占了本厂资源，
        不重排时段保留的原安排按现在的资料已不成立。返回 (阻断原因, 提醒, {工序: 保留标记}, 保留安排结果)。"""
        capture = cast("ProductionFactsCapture", self.facts.capture)
        version = max((row["version"] for row in capture.table("ScheduleHistory")), default=0)
        reasons = external_resource_issues(self.facts, operations, version)
        # 与排产计算查不重排时段的范围一致：这次要重排的工序，加上合并外协组按实际周期派生保留的成员。
        held_ids = {row["op_id"] for row in rows if row["status"] in ("eligible", "auto_assign_required")} | set(cycles)
        held, notes, marks, held_obj = held_arrangement_reasons(
            self.facts, checks, settings, version, batches, operations,
            held_ids, cycles, projections, hold_window_bounds=hold_window_bounds,
        )
        return reasons + held, notes, marks, held_obj

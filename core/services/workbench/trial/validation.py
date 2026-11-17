"""Live constraints over saved original work, using the unique execution ledger."""

from __future__ import annotations

from datetime import datetime

from core.errors import AppError
from core.models.content import same
from core.models.workbench_run_compute import CandidateRunInputError
from core.models.workbench_trial import issue, reject, validation
from core.services.workbench.facts.archived_calendar import ArchivedCalendar
from core.services.workbench.run.candidate_adoption_constraints import (
    DraftScheduleEvaluation,
    evaluate_draft_schedule_constraints,
)
from core.services.workbench.run.input_runtime import HeldArrangements
from core.services.workbench.run.schedule_occupancy_constraints import latest_schedule_rows

from .arrangements import same_arrangement
from .calendar import estimate, new_slot_effort
from .constraints import build_trial_intervals
from .execution_anchors import resolve_execution_anchors
from .facts import facts_unchanged
from .materials import adoption_settings, hold_settings, run_policy
from .piece_scope import evaluate_trial_piece_scope
from .protection import TrialProtection, frozen_issue, keeps_frozen, prepare_frozen_arrangements


class TrialValidator:
    def __init__(self, admission, rows, live, *, resolved_anchors=None):
        self.admission, self.rows, self.live = admission, rows, live
        self.source = live["origin"].source
        self.tables = live["facts"]["tables"]
        self.checks = live["preflight_facts"].checks()
        self.calendar = ArchivedCalendar(self.tables, metadata_basis="current_transaction_snapshot")
        self.engine = self.calendar.engine
        self.qualification = live["resource_facts"]
        self.qualification_cache = {}
        self._protected_state = None
        self._hold_key = None
        self.anchors, self.anchor_error = (
            resolved_anchors if resolved_anchors is not None else resolve_execution_anchors(rows, live)
        )
        self.batch_ready_dates = {}
        self.trial_intervals: dict = {}

    def _protect(self, current_by_row):
        # 采用输入的起止日随试调行变化（不重排时段按它裁剪）：行改过就按当前各行重新找。
        # 只比较各行准入后的最早开始日与最晚结束日，并在冻结窗口口径未变时复用冻结原安排。
        span = (
            min(start for start, _end in current_by_row.values()).date().isoformat(),
            max(end for _start, end in current_by_row.values()).date().isoformat(),
        )
        if self._protected_state == span:
            return
        self._protected_state = span
        self.settings = adoption_settings(self.source, self.rows, self.checks, self.live["execution"], span=span)
        anchor = hold_settings(self.source, self.settings)
        hold_key = anchor["start_date"], anchor.get("hold_window")
        if self._hold_key == hold_key:
            return
        self._hold_key = hold_key
        self.frozen, self.frozen_issue = {}, None
        try:
            self.held = prepare_frozen_arrangements(self.rows, self.live, settings=self.settings)
        except CandidateRunInputError:
            # 唯一的领域拒绝：不重排时段里的零工时原安排与正式计划的依据对不上（point_evidence_unproven）。
            # 存储损坏与代码缺陷原样上抛；采用时的存储损坏翻译只在 adoption_validation 一处。
            self.held = HeldArrangements(set(), [], {})
            self.frozen_issue = issue(
                "locked_point_evidence_unproven",
                "正式采用要原样保留来源排产不重排时段里的原安排，但其中零工时原安排在正式计划里找不到对应依据，"
                "不能正式采用。请重新做排产检查，或把不重排时段改短或不设后再试。",
            )
        else:
            self.frozen = {
                seed["op_id"]: dict(seed, hold_window=self.held.meta["hold_window"])
                for seed in self.held.seed_results
            }
        self.protection = TrialProtection(self.live, self.frozen)

    def _admission_issues(self, *, check_baseline=True):
        issues = []
        if not facts_unchanged(self.admission, self.live):
            issues.append(issue("trial_facts_changed", "建草稿之后现场数据变了；草稿里的工序和对比基准没变，不能按旧数据正式采用。"))
        if check_baseline and not same(self.admission["baseline"], self.live["baseline"]):
            issues.append(issue("trial_baseline_changed", "建草稿时的正式计划已经变了，草稿没有自动切到最新计划。"))
        return issues

    def evaluate_constraints(self, *, check_baseline: bool = True) -> DraftScheduleEvaluation:
        return self._evaluate_draft(self._admission_issues(check_baseline=check_baseline))

    def evaluate_saved(self, *, check_baseline=True):
        return validation(list(self.evaluate_constraints(check_baseline=check_baseline).issues))

    def evaluate_current(self):
        """The caller just captured this admission from the same live context."""
        return validation(list(self._evaluate_draft([]).issues))

    def _estimate_row(self, row, start, point_proven):
        return estimate(
            self.engine, row["original"], row["current"], start=start, point_proven=point_proven
        )

    def prepare_validation_context(self, admission_issues):
        self.trial_intervals = build_trial_intervals(self.rows, reported=self.live["execution_reported"])
        self._protect(self.trial_intervals["current_by_row"])
        latest_schedule = latest_schedule_rows(self.live["facts"]["tables"]["Schedule"])
        piece_scope, piece_issues = evaluate_trial_piece_scope(self.rows, self.live, self.settings)
        base_issues = self.admission["base_issues"] + admission_issues
        if self.frozen_issue:
            base_issues.append(self.frozen_issue)
        if self.anchor_error:
            base_issues.append(self.anchor_error)
        return {
            "live": self.live,
            "checks": self.checks,
            "settings": self.settings,
            "material_policy_base": run_policy(self.source),
            "qualification": self.qualification,
            "qualification_cache": self.qualification_cache,
            "anchors": self.anchors,
            "batch_ready_dates": self.batch_ready_dates,
            "trial_intervals": self.trial_intervals,
            "latest_schedule": latest_schedule,
            "piece_scope": piece_scope,
            "piece_issues": piece_issues,
            "estimate_fn": self._estimate_row,
            "base_issues": base_issues,
            "row_protections": {row["row_ref"]: self._row_protection(row) for row in self.rows},
        }

    def _evaluate_draft(self, admission_issues) -> DraftScheduleEvaluation:
        context = self.prepare_validation_context(admission_issues)
        return evaluate_draft_schedule_constraints(self.calendar, self.rows, context=context)

    def _row_protection(self, row):
        original, current = row["original"], row["current"]
        issues = []
        protected = self.protection.check(row)
        anchor = self.anchors.get(original["operation"]["id"])
        if anchor is not None and not same_arrangement(current, anchor["arrangement"]):
            issues.append(
                issue(
                    "scenario_execution_anchor_outdated",
                    "这份试调保留的时间或资源与实际报工不同，请从当前正式计划重新发起试调。",
                    row["task_ref"],
                )
            )
        if protected and protected["code"] == "task_frozen":
            seed = self.frozen[original["operation"]["id"]]
            if not keeps_frozen(row, seed, self.trial_intervals["current_by_row"][row["row_ref"]]):
                issues.append(frozen_issue(row, seed, changed=True))
            return issues, None, seed
        if protected:
            expected = anchor["arrangement"] if anchor is not None else original["arrangement"]
            if protected["code"] != "execution_protected" or (
                anchor is None and not same_arrangement(current, expected)
            ):
                issues.append(protected)
        return issues, protected, None

    def adjusted(self, row, intent):
        # 能不能改这一行、原工时依据是否成立，按改之前这一版各行准入后的起止判断；改完由 evaluate_saved 重新准入新的一版。
        before = build_trial_intervals(self.rows, reported=self.live["execution_reported"])
        self._protect(before["current_by_row"])
        protected = self.protection.check(row)
        if protected:
            reject(protected["code"], protected["message"])
        current = self._requested_arrangement(intent)
        if row["original"]["operation"]["source"] == "external" and any(
            intent[key] is not None for key in ("machine_ref", "operator_ref")
        ):
            reject("external_internal_resource", "外协工序必须明确使用空内部资源。", 422)
        effort = new_slot_effort(row["original"])
        end = self._adjusted_end(row, current, effort, point_proven=row["row_ref"] in before["original_points_by_row"])
        current["end"] = end.isoformat()
        if same_arrangement(row["current"], current):
            return row["current"]
        current["operation_effort"] = dict(effort.to_dict(), operation_ref=row["operation_ref"])
        return current

    def _requested_arrangement(self, intent):
        refs = {item["ref"]: item for item in self.tables["WorkbenchEntityRefs"] if item["active"] == 1}
        current = {"start": intent["start"]}
        for kind in ("machine", "operator"):
            ref = intent[kind + "_ref"]
            entity = refs.get(ref)
            if ref is not None and (entity is None or entity["kind"] != kind):
                reject("entity_not_found", "所选设备或人员不存在、已被替换或类型不对。", 404)
            current[kind + "_ref"] = ref
            current[kind + "_id"] = entity["entity_key"] if entity else None
        return current

    def _adjusted_end(self, row, current, effort, *, point_proven):
        # 开始时刻已由 change_input 准入成工厂本地时间的规范写法。
        start = datetime.fromisoformat(current["start"])
        try:
            estimated_start, end = estimate(
                self.engine, row["original"], current, start=start, point_proven=point_proven, effort=effort
            )
        except AppError:
            # 日历引擎的领域拒绝：班次里找不到可排时间、越过可表示日期、日历资料不合规则。
            # estimate 自己的拒绝、存储损坏与代码缺陷不是 AppError，原样上抛。
            reject("calendar_unproven", "真实日历或原工时不能计算完工时间，本次调整未写入。", 422)
        if row["original"].get("point_basis") is not None and estimated_start != start:
            reject("point_calendar_conflict", "所选点时间不在允许班次内，未推迟完工或改成正时长，原草稿保留。", 422)
        return end

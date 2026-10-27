"""Live constraints over saved original work, using the unique execution ledger."""

from datetime import datetime

from core.errors import AppError
from core.models.content import content_text, same
from core.models.resource_capabilities import supports_source
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_compute import CandidateRunInputError
from core.models.workbench_trial import issue, reject, validation
from core.services.personnel.operator_qualification import OperatorQualificationError
from core.services.workbench.facts.stored_algo_inputs import stored_operation
from core.services.workbench.run.input_runtime import HeldArrangements
from core.services.workbench.run.piece_adoption_trial import trial_piece_issues

from .arrangements import same_arrangement
from .calendar import calendar_engine, estimate, new_slot_effort
from .constraints import interval, relation_issues, resource_issues
from .execution_anchors import resolve_execution_anchors
from .facts import facts_unchanged
from .materials import adoption_settings, hold_settings, material_issues
from .protection import TrialProtection, frozen_issue, frozen_note, keeps_frozen, prepare_frozen_arrangements


class TrialValidator:
    def __init__(self, conn, admission, rows, live):
        self.conn, self.admission, self.rows, self.live = conn, admission, rows, live
        self.tables = live["facts"]["tables"]
        self.checks = live["preflight_facts"].checks()
        self.engine = calendar_engine(self.tables)
        self.calendar_issue = None if self.engine is not None else issue(
            "calendar_unproven", "日历数据无效，请核对工作日历。")
        self.qualification = live["resource_facts"]
        self.qualification_cache = {}
        self._protected_state = None
        self._hold_key = None
        # 建草稿时已在同一份现场资料上算过报工固定安排；读取已有草稿时这里现算。
        prepared_anchors = live.get("execution_anchors")
        self.anchors, self.anchor_error = (prepared_anchors if prepared_anchors is not None
                                           else resolve_execution_anchors(conn, rows, live))
        self.downtime = {}
        for row in self.tables["MachineDowntimes"]:
            self.downtime.setdefault(row["machine_id"], []).append(row)

    def _protect(self):
        # 采用输入的起止日随试调行变化（不重排时段按它裁剪）：行改过就按当前各行重新找。
        # 只比较各行的最早开始日与最晚结束日，并在冻结窗口口径未变时复用冻结原安排。
        span = (min(row["current"]["start"][:10] for row in self.rows),
                max(row["current"]["end"][:10] for row in self.rows))
        if self._protected_state == span:
            return
        self._protected_state = span
        self.settings = adoption_settings(self.admission, self.rows, self.checks, self.live["execution"])
        anchor = hold_settings(self.admission, self.settings)
        hold_key = anchor["start_date"], anchor.get("hold_window")
        if self._hold_key == hold_key:
            return
        self._hold_key = hold_key
        self.frozen, self.frozen_issue = {}, None
        try:
            self.held = prepare_frozen_arrangements(self.admission, self.rows, self.live,
                                                   settings=self.settings)
        except (AppError, CandidateRunInputError, ValueError):
            self.held = HeldArrangements(set(), [], {})
            self.frozen_issue = issue("freeze_window_unavailable", "正式采用要原样保留来源排产不重排时段里的原安排，"
                                      "但正式计划里这段时间的安排读不出来或者对不上，不能正式采用。请联系维护人员核对正式计划。")
        else:
            self.frozen = {seed["op_id"]: dict(seed, hold_window=self.held.meta["hold_window"])
                           for seed in self.held.seed_results}
        self.protection = TrialProtection(self.live, self.frozen)

    def evaluate_saved(self, *, check_baseline=True):
        issues = []
        if not facts_unchanged(self.admission, self.live):
            issues.append(issue("trial_facts_changed", "建草稿之后现场数据变了；草稿里的工序和对比基准没变，不能按旧数据正式采用。"))
        if check_baseline and not same(self.admission["baseline"], self.live["baseline"]):
            issues.append(issue("trial_baseline_changed", "建草稿时的正式计划已经变了，草稿没有自动切到最新计划。"))
        return self._evaluate(issues)

    def evaluate_current(self):
        """The caller just captured this admission from the same live context."""
        return self._evaluate([])

    def _evaluate(self, admission_issues):
        self._protect()
        issues = list(self.admission["base_issues"]) + admission_issues
        if self.calendar_issue:
            issues.append(self.calendar_issue)
        if self.frozen_issue:
            issues.append(self.frozen_issue)
        if self.anchor_error:
            issues.append(self.anchor_error)
        for row in self.rows:
            issues.extend(self._row(row))
        issues.extend(relation_issues(self.rows, self.live))
        issues.extend(trial_piece_issues(self.rows, self.live, self.settings))
        issues.extend(resource_issues(self.rows, self.live, conn=self.conn))
        unique = {content_text(item): item for item in issues}
        return validation(list(unique.values()))

    def _row(self, row):
        original, current = row["original"], row["current"]
        issues = []
        protected = self.protection.check(row)
        anchor = self.anchors.get(original["operation"]["id"])
        if anchor is not None and not same_arrangement(current, anchor["arrangement"]):
            issues.append(issue("scenario_execution_anchor_outdated", "这份试调保留的时间或资源与实际报工不同，请从当前正式计划重新发起试调。", row["task_ref"]))
        if protected and protected["code"] == "task_frozen":
            return issues + self._frozen_row(row, self.frozen[original["operation"]["id"]])
        if protected:
            expected = anchor["arrangement"] if anchor is not None else original["arrangement"]
            if protected["code"] != "execution_protected" or (anchor is None and not same_arrangement(current, expected)):
                issues.append(protected)
        issues.extend(self._resources(row))
        issues.extend(self._times(row, protected))
        if protected is None:
            issues.extend(material_issues(self.admission, self.checks, row))
        return issues

    def _frozen_row(self, row, seed):
        """按时段保留的工序试调不能改，但照常核对这个安排现在还成不成立（正式采用同样逐条复核）；
        不成立的，提示里说清楚为什么改不了、该怎么办，免得反复重新核对也过不去。"""
        issues = [] if keeps_frozen(row, seed) else [frozen_issue(row, seed, changed=True)]
        found = self._resources(row) + self._times(row, None) + material_issues(self.admission, self.checks, row)
        return issues + [frozen_note(item, seed) for item in found]

    def _resources(self, row):
        original, current, ref = row["original"], row["current"], row["task_ref"]
        op = dict(original["operation"], machine_id=current["machine_id"], operator_id=current["operator_id"])
        batch = original["batch"]
        if op["id"] in self.anchors:
            return [dict(item, task_ref=ref, severity="blocker") for item in self.checks.protected_resources(op)]
        issues = [dict(item, task_ref=ref, severity="blocker") for item in self.checks.fields(batch, op) + self.checks.resources(op)]
        if batch["priority"] not in ("normal", "urgent", "critical"):
            issues.append(issue("priority_unknown", "原批次优先级无效，请核对批次资料。", ref))
        issues.extend(self._qualification(op, ref))
        if op["source"] == "external" and (current["machine_ref"] is not None or current["operator_ref"] is not None):
            issues.append(issue("external_internal_resource", "外协工序不能带内部设备人员安排。", ref))
        return issues

    def _times(self, row, protected):
        original, current, ref = row["original"], row["current"], row["task_ref"]
        batch, issues = original["batch"], []
        anchor = self.anchors.get(original["operation"]["id"])
        actual = anchor is not None and anchor["basis"] == "completed_actuals"
        fixed_cycle = anchor is not None and anchor["basis"] == "merged_external_actuals"
        try:
            start, end = interval(current, original=original)
            if protected is None and self.engine is not None:
                estimated_start, estimated_end = estimate(self.engine, original, current)
                if start != estimated_start or end != estimated_end:
                    issues.append(issue("calendar_duration_conflict", "开完工与原工时、真实日历或效率不一致。", ref))
            if (not actual and not fixed_cycle and self.settings["ready_check"]
                    and batch["ready_date"] and start < datetime.fromisoformat(batch["ready_date"])):
                issues.append(issue("before_ready_date", "安排早于原批次可开工日期。", ref))
            if not actual:
                issues.extend(self._downtimes(row, start, end))
        except WorkbenchCommandRejected as exc:
            issues.append(issue(exc.code, str(exc), ref))
        except (AppError, ValueError, TypeError, OverflowError):
            issues.append(issue("calendar_unproven", "原工时、真实班次、日期或停机数据无效，未用默认数补齐。", ref))
        return issues

    def _downtimes(self, row, start, end):
        issues, ref = [], row["task_ref"]
        if start == end:
            return issues
        for downtime in self.downtime.get(row["current"]["machine_id"], []):
            if downtime["status"] == "cancelled":
                continue
            if downtime["status"] != "active":
                issues.append(issue("downtime_state_unknown", "设备停机状态不明确。", ref))
            elif datetime.fromisoformat(downtime["start_time"]) < end and datetime.fromisoformat(downtime["end_time"]) > start:
                issues.append(issue("machine_downtime", "目标安排与实际设备停机重叠。", ref))
        return issues

    def _qualification(self, op, ref):
        if op["source"] != "internal" or not op["operator_id"]:
            return []
        kind = self.checks.catalogs["op_type"].get(op["op_type_id"])
        if kind is None or not supports_source(kind["category"], "internal"):
            return [issue("work_type_invalid", "自制工序需要真实自制工种。", ref)]
        key = op["operator_id"], op["machine_id"], op["op_type_id"]
        if key not in self.qualification_cache:
            try:
                self.qualification.validate_fixed(self.conn, [stored_operation(op)])
                result = None
            except OperatorQualificationError:
                result = issue("operator_qualification_invalid", "人员工种资格或设备操作授权不符合真实登记。")
            self.qualification_cache[key] = result
        result = self.qualification_cache[key]
        return [dict(result, task_ref=ref)] if result else []

    def adjusted(self, row, intent):
        self._protect()
        protected = self.protection.check(row)
        if protected:
            reject(protected["code"], protected["message"])
        if self.engine is None:
            reject("calendar_unproven", "当前日历不能计算完工时间，本次调整未写入。", 422)
        current = self._requested_arrangement(intent)
        if row["original"]["operation"]["source"] == "external" and any(intent[key] is not None for key in ("machine_ref", "operator_ref")):
            reject("external_internal_resource", "外协工序必须明确使用空内部资源。", 422)
        effort = new_slot_effort(row["original"])
        end = self._adjusted_end(row, current, effort)
        current["end"] = end.isoformat()
        if same_arrangement(row["current"], current):
            return dict(row["current"])
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

    def _adjusted_end(self, row, current, effort):
        try:
            estimated_start, end = estimate(self.engine, row["original"], current, effort=effort)
            if row["original"].get("point_basis") is not None and estimated_start != datetime.fromisoformat(current["start"]):
                reject("point_calendar_conflict", "所选点时间不在允许班次内，未推迟完工或改成正时长，原草稿保留。", 422)
        except (AppError, ValueError, TypeError, OverflowError) as exc:
            if isinstance(exc, WorkbenchCommandRejected):
                raise
            reject("calendar_unproven", "真实日历或原工时不能计算完工时间，本次调整未写入。", 422)
        return end

"""Live constraints over saved original work, using the unique execution ledger."""

from datetime import datetime

from core.errors import AppError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial import issue, reject, validation
from core.models.workbench_trial_codec import fingerprint
from core.services.personnel.operator_qualification import OperatorQualificationError, OperatorQualificationService
from core.services.workbench.preflight_checks import PreflightChecks

from .piece_adoption_trial import trial_piece_issues
from .trial_calendar import calendar_engine, estimate
from .trial_constraints import interval, relation_issues, resource_issues
from .trial_execution_anchors import anchor_issue, execution_anchors
from .trial_protection import TrialProtection
from .zero_duration_evidence import trial_point_evidence


class TrialValidator:
    def __init__(self, conn, admission, rows, live):
        self.conn, self.admission, self.rows, self.live = conn, admission, rows, live
        self.tables = live["facts"]["tables"]
        self.checks = PreflightChecks(self.tables)
        self.calendar_issue = None
        try:
            self.engine = calendar_engine(self.tables)
        except (AppError, ValueError, TypeError, OverflowError):
            self.engine = None
            self.calendar_issue = issue("calendar_unproven", "日历数据无效，请核对工作日历。")
        self.qualification = OperatorQualificationService(conn)
        self.qualification_cache = {}
        self.ops = {row["id"]: row for row in self.tables["BatchOperations"]}
        self.protection = TrialProtection(live)
        self.anchors, self.anchor_error = {}, None
        try:
            self.anchors = execution_anchors(conn, rows, live)
        except (AppError, ValueError, TypeError, KeyError, OverflowError) as exc:
            self.anchor_error = anchor_issue(exc)
        self.downtime = {}
        for row in self.tables["MachineDowntimes"]:
            self.downtime.setdefault(row["machine_id"], []).append(row)

    def evaluate(self):
        issues = list(self.admission["base_issues"])
        if self.calendar_issue:
            issues.append(self.calendar_issue)
        if self.anchor_error:
            issues.append(self.anchor_error)
        if any(row["operation_ref"] is None or row["recorded_against_task_ref"] is None
               for row in self.tables["WorkbenchExecutionLegacyFacts"]):
            issues.append(issue("execution_scope_unproven", "保留的历史报工记录里有对不上工序的记录，这里没有忽略它们。"))
        if self.admission["facts_hash"] != self.live["facts_hash"]:
            issues.append(issue("trial_facts_changed", "建草稿之后现场数据变了；草稿里的工序和对比基准没变，不能按旧数据正式采用。"))
        if fingerprint(self.admission["baseline"]) != fingerprint(self.live["baseline"]):
            issues.append(issue("trial_baseline_changed", "建草稿时的正式计划已经变了，草稿没有自动切到最新计划。"))
        for row in self.rows:
            issues.extend(self._row(row))
        issues.extend(relation_issues(self.rows, self.live))
        issues.extend(trial_piece_issues(self.rows, self.live))
        issues.extend(resource_issues(self.rows, self.live, conn=self.conn))
        unique = {fingerprint(item): item for item in issues}
        return validation(list(unique.values()))

    def _row(self, row):
        original, current = row["original"], row["current"]
        issues = []
        protected = self.protection.check(row)
        anchor = self.anchors.get(original["operation"]["id"])
        if anchor is not None and current != anchor["arrangement"]:
            issues.append(issue("scenario_execution_anchor_outdated", "这份试调保留的时间或资源与实际报工不同，请从当前正式计划重新发起试调。", row["task_ref"]))
        if protected:
            expected = anchor["arrangement"] if anchor is not None else original["arrangement"]
            if protected["code"] not in ("task_locked", "execution_protected") or (anchor is None and current != expected):
                issues.append(protected)
        issues.extend(self._resources(row))
        issues.extend(self._times(row, protected))
        return issues

    def _resources(self, row):
        original, current, ref = row["original"], row["current"], row["task_ref"]
        op = dict(original["operation"], machine_id=current["machine_id"], operator_id=current["operator_id"])
        batch = original["batch"]
        issues = [dict(item, task_ref=ref, severity="blocker") for item in self.checks.fields(batch, op) + self.checks.resources(op)]
        if batch["priority"] not in ("normal", "urgent", "critical"):
            issues.append(issue("priority_unknown", "原批次优先级无效，请核对批次资料。", ref))
        issues.extend(self._qualification(op, ref))
        if op["source"] == "external" and (current["machine_ref"] is not None or current["operator_ref"] is not None):
            issues.append(issue("external_internal_resource", "外协工序不能带内部设备人员安排。", ref))
        issues.extend(dict(item, task_ref=ref, severity="warning") for item in self.checks.readiness(batch, True))
        return issues

    def _times(self, row, protected):
        original, current, ref = row["original"], row["current"], row["task_ref"]
        batch, issues = original["batch"], []
        try:
            start, end = interval(current, original=original)
            if protected is None and self.engine is not None:
                estimated_start, estimated_end = estimate(self.engine, original, current)
                if start != estimated_start or end != estimated_end:
                    issues.append(issue("calendar_duration_conflict", "开完工与原工时、真实日历或效率不一致。", ref))
            if batch["ready_date"] and start < datetime.fromisoformat(batch["ready_date"]):
                issues.append(issue("before_ready_date", "安排早于原批次可开工日期。", ref))
            issues.extend(self._downtimes(row, start, end))
        except WorkbenchCommandRejected as exc:
            issues.append(issue(exc.code, str(exc), ref))
        except (AppError, ValueError, TypeError, OverflowError):
            issues.append(issue("calendar_unproven", "原工时、真实班次、日期或停机数据无效，未用默认数补齐。", ref))
        return issues

    def _downtimes(self, row, start, end):
        issues, ref = [], row["task_ref"]
        if start == end:
            trial_point_evidence(row["original"], row["current"])
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
        if kind is None or kind["category"] != "internal":
            return [issue("work_type_invalid", "自制工序需要真实自制工种。", ref)]
        key = op["operator_id"], op["machine_id"], op["op_type_id"]
        if key not in self.qualification_cache:
            try:
                self.qualification.require(operator_id=key[0], machine_id=key[1], op_type_id=key[2])
                result = None
            except OperatorQualificationError:
                result = issue("operator_qualification_invalid", "人员工种资格或设备操作授权不符合真实登记。")
            self.qualification_cache[key] = result
        result = self.qualification_cache[key]
        return [dict(result, task_ref=ref)] if result else []

    def adjusted(self, row, intent):
        protected = self.protection.check(row)
        if protected:
            reject(protected["code"], protected["message"])
        if self.engine is None:
            reject("calendar_unproven", "当前日历不能计算完工时间，本次调整未写入。", 422)
        current = self._requested_arrangement(intent)
        if row["original"]["operation"]["source"] == "external" and any(intent[key] is not None for key in ("machine_ref", "operator_ref")):
            reject("external_internal_resource", "外协工序必须明确使用空内部资源。", 422)
        end = self._adjusted_end(row, current)
        current["end"] = end.isoformat(timespec="seconds")
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

    def _adjusted_end(self, row, current):
        try:
            estimated_start, end = estimate(self.engine, row["original"], current)
            if row["original"].get("point_basis") is not None and estimated_start != datetime.fromisoformat(current["start"]):
                reject("point_calendar_conflict", "所选点时间不在允许班次内，未推迟完工或改成正时长，原草稿保留。", 422)
        except (AppError, ValueError, TypeError, OverflowError) as exc:
            if isinstance(exc, WorkbenchCommandRejected):
                raise
            reject("calendar_unproven", "真实日历或原工时不能计算完工时间，本次调整未写入。", 422)
        return end

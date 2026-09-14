"""In-memory batch simulation. No SQL writes, including preview and import checks."""

import copy
from typing import Dict, List, NoReturn, Optional

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_execution_input import (
    REPORT_FIELDS,
    normalize_report_input,
    public_ref,
    reject,
    validate_actual_values,
)
from data.repositories.workbench_execution_report_repo import new_ref

from .production_report_validation import (
    ReportResourceValidator,
    correction_conflicts,
    require_current,
    validate_legacy_link,
    validate_projection_change,
)


class ReportBatchRejected(WorkbenchCommandRejected):
    def __init__(self, code: str, message: str, status: int = 409, *,
                 row_number: Optional[int] = None, conflicts: Optional[List[Dict[str, str]]] = None):
        super().__init__(code, message, status)
        self.row_number = row_number
        self.conflicts = [] if conflicts is None else conflicts


def _reject_row(error: WorkbenchCommandRejected, row_number: int) -> NoReturn:
    if isinstance(error, ReportBatchRejected):
        error.row_number = row_number
        raise error
    raise ReportBatchRejected(error.code, str(error), error.status, row_number=row_number) from error


def normalize_items(items):
    if not isinstance(items, list) or not 1 <= len(items) <= 5000:
        reject("一次报工要填 1 到 5000 行。请调整行数后重新提交。", status=400)
    result = []
    for index, item in enumerate(items, 1):
        try:
            if type(item) is not dict or set(item) != {"action", "ref", "payload"}:
                reject("报工行的内容不完整。请核对标红的项后重新提交。", status=400)
            result.append({"action": item["action"], "ref": public_ref(item["ref"]),
                           "payload": normalize_report_input(item["action"], item["payload"])})
        except WorkbenchCommandRejected as exc:
            _reject_row(exc, index)
    return result


def _merge(action, original, patch):
    values = dict(original)
    for key in REPORT_FIELDS:
        if key not in patch:
            continue
        if action == "supplement" and original.get(key) not in (None, "") and original[key] != patch[key]:
            reject("已有的报工记录不能用「补齐」盖掉。请改用「更正」。", "constraint_conflict", 409)
        values[key] = patch[key]
    return values


def _new_row(item, operation_ref, task, *, actor, now, row_number):
    payload = item["payload"]
    return {"report_ref": new_ref(), "report_no": payload.get("report_no") or f"preview-{row_number:08d}",
            "allocate_number": "report_no" not in payload, "operation_ref": operation_ref,
            "recorded_against_task_ref": task["task_ref"], "recorded_against_plan_ref": task["plan_ref"],
            "source": payload["source"], "legacy_fact_ref": payload.get("legacy_fact_ref"), "recorded_at": now,
            "revision_ref": new_ref(), "sequence": 1, "previous_revision_ref": None, "action": "create",
            "values": {key: payload.get(key, "" if key == "remark" else None) for key in REPORT_FIELDS},
            "reason": payload.get("reason", ""), "local_operator": actor, "declared_operator": payload["declared_operator"],
            "revision_at": now, "receipt_ref": None}


class ReportBatchPreparation:
    def __init__(self, ledger, items, actor):
        self.ledger, self.items, self.actor = ledger, items, actor
        self.conn = ledger.conn
        self.resources = ReportResourceValidator(self.conn)
        self.resolved = []
        self.appended, self.rows = [], []
        self.by_number = {}

    def _resolve_rows(self):
        repo = self.ledger.repo
        task_headers = repo.task_headers({item["ref"] for item in self.items if item["action"] == "create"})
        report_headers = repo.report_headers({item["ref"] for item in self.items if item["action"] != "create"})
        for index, item in enumerate(self.items, 1):
            row = (task_headers if item["action"] == "create" else report_headers).get(item["ref"])
            if row is None:
                raise ReportBatchRejected("entity_not_found", "这道工序的安排或原报工记录不存在。请刷新后重新选择。", 404, row_number=index)
            self.resolved.append(row)

    def _preload_resources(self):
        fields = ("actual_machine_ref", "actual_operator_ref")
        refs = {item["payload"][field] for item in self.items for field in fields if item["payload"].get(field)}
        refs.update(history[-1]["values"][field] for group in self.facts["reports"].values()
                    for history in group.values() for field in fields if history[-1]["values"].get(field))
        self.resources.preload(refs)

    def resolve(self):
        self._resolve_rows()
        repo = self.ledger.repo
        refs = list(dict.fromkeys(row["operation_ref"] for row in self.resolved))
        self.facts = self.ledger.load(refs)
        self.before = copy.deepcopy(self.facts)
        self._preload_resources()
        self.by_number = repo.report_headers({item["payload"]["report_no"] for item in self.items
                                             if item["payload"].get("report_no")}, by_number=True)
        for group in self.facts["reports"].values():
            for history in group.values():
                self.by_number[history[-1]["report_no"]] = history[-1]
        self.snapshot = {"input_hash": input_fingerprint(self.items), "operations": [
            self.ledger.fact_snapshot(self.before, ref) for ref in sorted(refs)]}

    def prepare(self):
        self.resolve()
        now = self.ledger.clock()
        before = {row.operation_ref: row for row in self.ledger.project_loaded(self.before, contexts=False)}
        self.before_projections = before
        for index, (item, resolved) in enumerate(zip(self.items, self.resolved), 1):
            try:
                self._row(item, resolved, index, now)
            except WorkbenchCommandRejected as exc:
                _reject_row(exc, index)
        self.projections = self.ledger.project_loaded(self.facts, contexts=False)
        changed_by_operation = {}
        for row in self.appended:
            changed_by_operation.setdefault(row["operation_ref"], []).append(row)
        for after in self.projections:
            changed = changed_by_operation.get(after.operation_ref, [])
            try:
                validate_projection_change(before[after.operation_ref], after)
                revisions = [row for row in changed if row["sequence"] > 1]
                conflicts = correction_conflicts(self.conn, self.ledger, self.facts, before[after.operation_ref], after, revisions) if revisions else []
                if conflicts:
                    raise ReportBatchRejected("constraint_conflict", "这次更正会影响后道工序或已采用的排产安排。请先处理下面列出的影响。", conflicts=conflicts)
            except WorkbenchCommandRejected as exc:
                _reject_row(exc, max(row["row_number"] for row in self.rows if row["operation_ref"] == after.operation_ref))
        return self

    def _row(self, item, resolved, index, now):
        operation_ref = resolved["operation_ref"]
        task = require_current(self.facts, operation_ref, item["ref"] if item["action"] == "create" else None)
        history, action = self._history(item, operation_ref)
        old = history[-1] if history else None
        if old is None:
            if self.before_projections[operation_ref].completion_basis == "complete_reports":
                reject("这道工序已经报完工，用「新增」不能把完工撤掉。请改用「更正」并填写原因。", "constraint_conflict", 409)
            if self.before_projections[operation_ref].completion_basis == "legacy_finish_event" and not item["payload"].get("legacy_fact_ref"):
                reject("这道工序已有历史完工记录，「补齐」必须指明补的是哪一条，不能凭空加产量。请选定要补齐的记录。", "constraint_conflict", 409)
            row = _new_row(item, operation_ref, task, actor=self.actor, now=now.isoformat(timespec="seconds"), row_number=index)
        else:
            row = dict(old, revision_ref=new_ref(), sequence=old["sequence"] + 1, previous_revision_ref=old["revision_ref"],
                       action=action, values=_merge(action, old["values"], item["payload"]),
                       reason=item["payload"].get("reason", "Excel explicit sparse supplement"),
                       local_operator=self.actor, declared_operator=item["payload"]["declared_operator"],
                       revision_at=now.isoformat(timespec="seconds"), receipt_ref=None)
        validate_actual_values(row["values"], now)
        self.resources.validate(self.facts["operations"][operation_ref], row["values"])
        validate_legacy_link(self.facts["legacy"].get(operation_ref, []), row["legacy_fact_ref"], row["values"])
        if old and row["values"] == old["values"]:
            self.rows.append(self._result(index, item, old, "unchanged", action=action))
            return
        self._check_link_unique(row)
        group = self.facts["reports"].setdefault(operation_ref, {})
        group.setdefault(row["report_ref"], []).append(row)
        self.appended.append(row)
        self.by_number[row["report_no"]] = row
        self.rows.append(self._result(index, item, row, "committed"))

    def _history(self, item, operation_ref):
        group = self.facts["reports"].get(operation_ref, {})
        if item["action"] != "create":
            history = group[item["ref"]]
            if history[-1]["revision_ref"] != item["payload"]["original_revision_ref"]:
                reject("这条报工记录已经被人改过。请刷新后重新核对再更正。", "stale_write", 409)
            return history, item["action"]
        number = item["payload"].get("report_no")
        row = self.by_number.get(number)
        if row is not None:
            if row["operation_ref"] != operation_ref:
                reject("这个报工单号已经属于另一道工序，不能改到当前工序。请换一个单号。", "constraint_conflict", 409)
            if item["payload"]["source"] != "excel":
                reject("这个报工单号已经有了。请改用「补齐」或「更正」。", "constraint_conflict", 409)
            if row["legacy_fact_ref"] != item["payload"].get("legacy_fact_ref"):
                reject("重复导入把历史记录的关联改掉了，系统不会自动重新对应来源。请核对后重新提交。", "constraint_conflict", 409)
            return group[row["report_ref"]], "supplement"
        return [], "create"

    def _check_link_unique(self, row):
        link = row["legacy_fact_ref"]
        if link and any(history[-1]["legacy_fact_ref"] == link and ref != row["report_ref"]
                        for ref, history in self.facts["reports"].get(row["operation_ref"], {}).items()):
            reject("这条历史记录已经补过报工了，不能重复累计。请核对后重新提交。", "constraint_conflict", 409)

    @staticmethod
    def _result(index, item, row, result, action=None):
        return {"row_number": index, "action": action or row["action"], "ref": item["ref"], "report_ref": row["report_ref"],
                "report_no": row["report_no"], "revision_ref": row["revision_ref"], "operation_ref": row["operation_ref"], "result": result}

    def public(self):
        return {"rows": self.rows, "summary": {"total": len(self.rows), "changed": len(self.appended),
                "unchanged": len(self.rows) - len(self.appended)}, "can_confirm": True, "snapshot": self.snapshot,
                "projections": [row.to_dict() for row in self.projections]}

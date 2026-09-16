"""Explicit report withdrawal through the same preview, receipt and ledger lock."""

import copy

from core.models.workbench_command import WorkbenchCommandOutcome, input_fingerprint
from core.models.workbench_execution_input import closed_write_context, normalize_report_void_input, reject
from data.repositories.workbench_execution_report_repo import WorkbenchExecutionReportRepository, new_ref

from .production_report_prepare import ReportBatchRejected
from .production_report_validation import (
    _successor_refs,
    correction_conflicts,
    require_current,
    validate_projection_change,
)
from .production_report_void_dependencies import adopted_quota_impacts


def _downstream_impacts(conn, ledger, facts, before, after, report):
    impacts = correction_conflicts(conn, ledger, facts, before, after, [report])
    refs = _successor_refs(conn, facts["operations"][before.operation_ref])
    downstream = ledger.project_operations(refs) if refs else []
    for row in downstream:
        if row.execution_state != "unreported" and not any(item["operation_ref"] == row.operation_ref for item in impacts):
            impacts.append({"code": "downstream_execution_exists", "operation_ref": row.operation_ref})
    labels = ledger.repo.operation_rows(list(dict.fromkeys(item["operation_ref"] for item in impacts))) if impacts else {}
    messages = {"downstream_execution_exists": "后道工序已有开工或报工记录",
                "downstream_requires_completion": "后道工序的执行或正式安排依赖本工序完工",
                "downstream_time_conflict": "后道工序时间与撤销后的完工记录冲突",
                "adopted_execution_basis_changed": "当前正式计划使用了这次报工的数量或开工事实",
                "adopted_completion_required": "当前正式计划依赖这次完工记录",
                "adopted_actual_resource_changed": "当前正式计划使用了这次报工的实际资源"}
    return [dict(item, operation_label=str(labels[item["operation_ref"]]["seq"]) + " " +
                 str(labels[item["operation_ref"]]["op_type_name"] or ""), message=messages[item["code"]]) for item in impacts]


class WorkbenchReportVoidService:
    def __init__(self, ledger, commands, actor_provider):
        self.ledger, self.commands, self.actor_provider = ledger, commands, actor_provider
        self.conn = ledger.conn

    def _prepare(self, payload):
        self.ledger.repo.require_schema()
        header = self.ledger.repo.report_header(report_ref=payload["report_ref"])
        if header is None:
            reject("原报工记录不存在，请刷新后重新选择。", "entity_not_found", 404)
        facts = self.ledger.load([header["operation_ref"]])
        history = facts["reports"].get(header["operation_ref"], {}).get(payload["report_ref"])
        if not history:
            reject("原报工的更正记录不完整，不能撤销。", "storage_failure", 500)
        original = history[-1]
        if original["revision_ref"] != payload["original_revision_ref"]:
            reject("这条报工已更正，请刷新后重新核对撤销内容。", "context_stale", 409)
        before = self.ledger.project_loaded(facts, contexts=False)[0]
        existing = facts["voids"].get(payload["report_ref"])
        snapshot = {"input_hash": input_fingerprint(payload),
                    "execution": self.ledger.fact_snapshot(facts, header["operation_ref"]),
                    "original_revision_ref": original["revision_ref"]}
        if existing:
            return {"target": original, "fact": existing, "before": before, "after": before,
                    "impacts": [], "snapshot": snapshot, "unchanged": True}
        require_current(facts, header["operation_ref"])
        actor = self.actor_provider()
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("Local application operator must be supplied by the server.")
        fact = dict(payload, void_fact_ref=new_ref(), local_operator=actor,
                    recorded_at=self.ledger.clock().isoformat(timespec="seconds"), receipt_ref=None)
        changed = copy.deepcopy(facts)
        changed["voids"][payload["report_ref"]] = fact
        after = self.ledger.project_loaded(changed, contexts=False)[0]
        validate_projection_change(before, after)
        impacts = _downstream_impacts(self.conn, self.ledger, facts, before, after, original)
        impacts += adopted_quota_impacts(self.conn, payload["report_ref"], header["operation_ref"])
        snapshot["dependencies"] = impacts
        return {"target": original, "fact": fact, "before": before, "after": after,
                "impacts": impacts, "snapshot": snapshot, "unchanged": False}

    def preview(self, report_ref, payload):
        normalized = normalize_report_void_input(report_ref, payload)
        with self.ledger.read_snapshot():
            prepared = self._prepare(normalized)
            context = closed_write_context()
            if not prepared["impacts"] and self.ledger.context_factory:
                context = self.ledger.context_factory(report_ref, ["report_void"], prepared["snapshot"])
            target = prepared["target"]
            return {"target_report": {"report_ref": report_ref, "report_no": target["report_no"],
                                      "original_revision_ref": target["revision_ref"], "values": target["values"]},
                    "before": prepared["before"].to_dict(), "after": prepared["after"].to_dict(),
                    "downstream_impacts": prepared["impacts"], "can_confirm": not prepared["impacts"],
                    "state": "voided" if prepared["unchanged"] else "active", "write_context": context,
                    "snapshot": prepared["snapshot"]}

    def execute(self, report_ref, payload, *, request_key, validate_context):
        normalized = normalize_report_void_input(report_ref, payload)

        def guard():
            prepared = self._prepare(normalized)
            validate_context(report_ref, "report_void", prepared["snapshot"])
            if prepared["impacts"]:
                raise ReportBatchRejected("constraint_conflict", "这次撤销会影响已有的后道执行或正式计划，请先处理列出的关联记录。",
                                          conflicts=prepared["impacts"])
            return prepared

        def mutate(prepared):
            fact = prepared["fact"]
            if not prepared["unchanged"]:
                WorkbenchExecutionReportRepository(self.conn).append_void(fact, request_key=request_key)
            return WorkbenchCommandOutcome("unchanged" if prepared["unchanged"] else "committed",
                {"report_ref": report_ref, "void_fact_ref": fact["void_fact_ref"], "state": "voided",
                 "refresh_required": True, "operation_refs": [prepared["before"].operation_ref]})

        return self.commands.execute(request_key=request_key, action="execution.report_void", context_ref=report_ref,
                                     normalized_input=normalized, guard=guard, mutate=mutate)

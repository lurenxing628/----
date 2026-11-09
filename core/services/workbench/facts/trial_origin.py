"""Immutable trial scope shared by delivery, operation views and saved archives."""

from collections import defaultdict
from typing import Any, Dict, NoReturn

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial import reject
from core.services.workbench.facts.candidate_facts import (
    batch_operation_rows,
    entity_ref_rows,
    index_rows,
    operation_ref_rows,
    operation_refs_by_id,
)
from core.services.workbench.facts.candidate_store import cached_generation_facts
from core.services.workbench.facts.preflight_dependencies import material_deferred_ids
from core.services.workbench.facts.trial_policy import TRIAL_FACTS_INVALID


def invalid_trial_snapshot() -> NoReturn:
    reject("trial_snapshot_invalid", TRIAL_FACTS_INVALID)


class TrialOrigin:
    """One trial source's members, prepared once from its admission and the rows' immutable originals.

    ``facts`` is the candidate source's GenerationFacts, or None for an official plan. ``batches`` maps
    the source batch references to their batches, ``operations`` groups every operation of the source by
    batch id and ``deferred`` holds the source's pending operation ids. ``unarranged`` holds the source
    batches' operations that no row arranges; ``operation_refs`` is the whole member scope, which every
    execution snapshot of the trial covers. Members depend only on originals, so a draft and its saved
    scenario share one origin, while ``contexts`` binds the rows of one stage.
    """

    def __init__(self, admission, rows):
        self.admission = admission
        source = admission["source"]
        if "capture" in source:
            try:
                self.facts = cached_generation_facts(source["capture"])
            except WorkbenchCommandRejected as exc:
                if exc.status == 413:
                    raise
                invalid_trial_snapshot()
        else:
            self.facts = None
        self.admission_operations: Dict[int, Dict[str, Any]] = batch_operation_rows(
            self._admission_table("BatchOperations"), on_corrupt=invalid_trial_snapshot
        )
        self.admission_refs_by_op_id: Dict[int, str] = operation_refs_by_id(
            operation_ref_rows(self._admission_table("WorkbenchPlanSourceRefs"), on_corrupt=invalid_trial_snapshot),
            on_corrupt=invalid_trial_snapshot,
        )
        self._delivery_scope(rows)
        self._unarranged(rows)
        self.operation_refs = frozenset(row["operation_ref"] for row in rows) | set(self.unarranged)

    def _admission_table(self, name):
        rows = self.admission["facts"]["tables"].get(name)
        if rows is None:
            invalid_trial_snapshot()
        return rows

    @property
    def archive(self):
        """The saved facts the source's resources and calendars were taken from."""
        return self.facts.archive if self.facts is not None else self.admission["facts"]

    @property
    def source_execution(self):
        """The source-time execution snapshot: candidate capture's or official admission's."""
        return self.facts.execution if self.facts is not None else self.admission.get("execution")

    def _delivery_scope(self, rows):
        source = self.admission["source"]
        if self.facts is not None:
            capture = source["capture"]
            selected = set(capture["input"]["batch_refs"])
            batches = {ref: self.facts.tables["Batches"][key] for (kind, key), ref in self.facts.entity_refs.items()
                       if kind == "batch" and ref in selected}
            operations = self.facts.tables["BatchOperations"].values()
            deferred = material_deferred_ids(source["dispositions"].values(), capture["input"])
            deferred_issues = []
        else:
            batches = {row["original"]["batch_ref"]: row["original"]["batch"] for row in rows}
            operations = self.admission_operations.values()
            # 正式计划来源在创建试调时就记下了原计划的待料工序编号与缺口。
            deferred, deferred_issues = set(source["deferred_operation_ids"]), source["deferred_operation_issues"]
            selected = {batch["batch_id"] for batch in batches.values()}
            pending = {operation["batch_id"] for operation in operations if operation["id"] in deferred} - selected
            if pending:
                batch_rows = index_rows(self._admission_table("Batches"), "batch_id", on_corrupt=invalid_trial_snapshot)
                entity_refs = entity_ref_rows(self._admission_table("WorkbenchEntityRefs"), on_corrupt=invalid_trial_snapshot)
                for batch_id in sorted(pending):
                    ref = entity_refs.get(("batch", batch_id))
                    if batch_id not in batch_rows or ref is None:
                        reject("trial_snapshot_invalid", "保存来源中待料批次的资料或永久编号缺失，请核对保存记录。")
                    batches[ref] = batch_rows[batch_id]
        by_batch = defaultdict(list)
        for operation in operations:
            by_batch[operation["batch_id"]].append(dict(operation, op_id=operation["id"]))
        self.batches, self.operations = batches, by_batch
        self.deferred, self.deferred_issues = deferred, deferred_issues

    def _unarranged(self, rows):
        if self.facts is not None:
            operations, refs = self.facts.tables["BatchOperations"], self.facts.operation_refs
        else:
            operations, refs = self.admission_operations, self.admission_refs_by_op_id
        self.refs_by_op_id = refs
        arranged = {row["operation_ref"] for row in rows}
        self.unarranged = {}
        for batch_ref, batch in self.batches.items():
            for item in self.operations[batch["batch_id"]]:
                op = operations[item["id"]]
                ref = refs.get(op["id"])
                if ref is None:
                    reject("trial_snapshot_invalid", "保存来源中的工序永久编号缺失，请核对保存记录。")
                if ref not in arranged:
                    self.unarranged[ref] = {"operation": op, "batch_ref": batch_ref, "batch": batch,
                                            "arranged": False, "deferred": op["id"] in self.deferred}

    def contexts(self, rows):
        """Bind one stage's rows and every member's source-time execution; arranged rows come first."""
        source = self.admission["source"]
        execution = self.source_execution
        if not isinstance(execution, dict):
            invalid_trial_snapshot()
        result = {row["operation_ref"]: {
            "operation": row["original"]["operation"], "batch_ref": row["original"]["batch_ref"],
            "batch": row["original"]["batch"], "row": row, "arranged": True,
            "deferred": row["original"]["operation"]["id"] in self.deferred,
            "execution": row["original"]["execution"]} for row in rows}
        for ref, member in self.unarranged.items():
            if ref not in execution:
                invalid_trial_snapshot()
            result[ref] = dict(member, execution=execution[ref])
        if self.facts is not None:
            dispositions = source.get("dispositions")
            if not isinstance(dispositions, dict):
                invalid_trial_snapshot()
            # 候选来源保存了所选批次全部工序的处置；正式计划来源没有处置。
            for ref, context in result.items():
                if ref not in dispositions:
                    invalid_trial_snapshot()
                context["disposition"] = dispositions[ref]
        return result

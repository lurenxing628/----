"""Immutable trial scope shared by delivery, operation views and saved archives."""

from collections import defaultdict

from core.models.workbench_trial import reject
from core.services.workbench.facts.candidate_store import cached_generation_facts
from core.services.workbench.facts.preflight_dependencies import material_deferred_ids


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
        self.facts = cached_generation_facts(source["capture"]) if "capture" in source else None
        self._delivery_scope(rows)
        self._unarranged(rows)
        self.operation_refs = frozenset(row["operation_ref"] for row in rows) | set(self.unarranged)

    @property
    def archive(self):
        """The saved facts the source's resources and calendars were taken from."""
        return self.facts.archive if self.facts is not None else self.admission["facts"]

    @property
    def source_execution(self):
        """The source-time execution snapshot: candidate capture's or official admission's."""
        return self.facts.execution if self.facts is not None else self.admission["execution"]

    def _delivery_scope(self, rows):
        admission, source = self.admission, self.admission["source"]
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
            operations = admission["facts"]["tables"]["BatchOperations"]
            # 正式计划来源在创建试调时就记下了原计划的待料工序编号与缺口。
            deferred, deferred_issues = set(source["deferred_operation_ids"]), source["deferred_operation_issues"]
            selected = {batch["batch_id"] for batch in batches.values()}
            pending = {operation["batch_id"] for operation in operations if operation["id"] in deferred} - selected
            if pending:
                tables = admission["facts"]["tables"]
                batch_rows = {batch["batch_id"]: batch for batch in tables["Batches"]}
                refs = {item["entity_key"]: item["ref"] for item in tables["WorkbenchEntityRefs"]
                        if item["kind"] == "batch" and item["active"] == 1}
                for batch_id in sorted(pending):
                    if batch_id not in batch_rows or batch_id not in refs:
                        reject("trial_snapshot_invalid", "保存来源中待料批次的资料或永久编号缺失，请核对保存记录。")
                    batches[refs[batch_id]] = batch_rows[batch_id]
        by_batch = defaultdict(list)
        for operation in operations:
            by_batch[operation["batch_id"]].append(dict(operation, op_id=operation["id"]))
        self.batches, self.operations = batches, by_batch
        self.deferred, self.deferred_issues = deferred, deferred_issues

    def _unarranged(self, rows):
        if self.facts is not None:
            operations, refs = self.facts.tables["BatchOperations"], self.facts.operation_refs
        else:
            tables = self.admission["facts"]["tables"]
            operations = {row["id"]: row for row in tables["BatchOperations"]}
            refs = {int(row["source_key"]): row["ref"] for row in tables["WorkbenchPlanSourceRefs"]
                    if row["kind"] == "operation" and row["active"] == 1}
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
        result = {row["operation_ref"]: {
            "operation": row["original"]["operation"], "batch_ref": row["original"]["batch_ref"],
            "batch": row["original"]["batch"], "row": row, "arranged": True,
            "deferred": row["original"]["operation"]["id"] in self.deferred,
            "execution": row["original"]["execution"]} for row in rows}
        for ref, member in self.unarranged.items():
            result[ref] = dict(member, execution=execution[ref])
        if self.facts is not None:
            # 候选来源保存了所选批次全部工序的处置；正式计划来源没有处置。
            for ref, context in result.items():
                context["disposition"] = source["dispositions"][ref]
        return result

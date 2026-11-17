"""Immutable trial scope shared by delivery, operation views and saved archives."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, NoReturn, Union

from core.models.workbench_trial import reject
from core.services.workbench.facts.archived_calendar import CALENDAR_TABLES
from core.services.workbench.facts.candidate_facts import (
    GenerationFacts,
    batch_operation_rows,
    entity_ref_rows,
    index_rows,
    operation_ref_rows,
    operation_refs_by_id,
)
from core.services.workbench.facts.preflight_dependencies import material_deferred_ids
from core.services.workbench.facts.production_capture import ArchivedTables

TRIAL_FACTS_INVALID = "试调草稿保存的现场资料已损坏，不能继续核对或采用，正式计划没有改变。请从当前正式计划重新发起试调。"


def invalid_trial_snapshot() -> NoReturn:
    reject("trial_snapshot_invalid", TRIAL_FACTS_INVALID)


@dataclass(frozen=True)
class OfficialTrialSource:
    """An official plan base as its draft stores it (``trial/base._plan_capture``): the slot types and suppliers it
    arranged, the plan's validated material policy and the pending work the plan recorded."""

    document: Dict[str, Any]
    # The run settings this source recorded, at this path under the admission's ``source``.
    settings_path: ClassVar[str] = "material_policy"

    @property
    def settings(self) -> Dict[str, Any]:
        return self.document["material_policy"]


@dataclass(frozen=True)
class CandidateTrialSource:
    """A candidate base as its draft stores it (``trial/base._candidate``), with the run archive the candidate was
    generated from: read with the candidate when the draft is created, read back from the run's records when a
    stored draft is loaded (``trial_policy.load_draft``); the draft itself stores only the run's ref."""

    document: Dict[str, Any]
    capture: Dict[str, Any]
    facts: GenerationFacts
    settings_path: ClassVar[str] = "capture.input"

    @property
    def settings(self) -> Dict[str, Any]:
        return self.capture["input"]


TrialSource = Union[OfficialTrialSource, CandidateTrialSource]


class TrialOrigin:
    """One trial source's members, prepared once from its typed source and the rows' immutable originals.

    ``tables`` reads the admission's environment tables by name: this transaction's ``LiveTables`` while the
    draft is being created, the stored admission's ``ArchivedTables`` (``saved``) afterwards.
    """

    def __init__(self, admission, rows, *, tables, source: TrialSource):
        self.admission = admission
        self.tables = tables
        self.source = source
        self.admission_operations: Dict[int, Dict[str, Any]] = batch_operation_rows(
            tables["BatchOperations"], on_corrupt=invalid_trial_snapshot
        )
        self.admission_refs_by_op_id: Dict[int, str] = operation_refs_by_id(
            operation_ref_rows(tables["WorkbenchPlanSourceRefs"], on_corrupt=invalid_trial_snapshot),
            on_corrupt=invalid_trial_snapshot,
        )
        self._delivery_scope(rows)
        self._unarranged(rows)
        self.operation_refs = frozenset(row["operation_ref"] for row in rows) | set(self.unarranged)

    @classmethod
    def saved(cls, admission, rows, source: TrialSource):
        """The origin of a stored draft admission and its source, both read by ``trial_policy.load_draft``."""
        return cls(admission, rows, tables=ArchivedTables(admission["facts"]), source=source)

    @property
    def calendar_tables(self):
        """The calendar tables the source's resources and calendars were taken from."""
        if isinstance(self.source, CandidateTrialSource):
            return {name: self.source.facts.table(name) for name in CALENDAR_TABLES}
        return {name: self.tables[name] for name in CALENDAR_TABLES}

    @property
    def source_execution(self):
        """The source-time execution snapshot: the candidate's run capture, or the draft admission's for an
        official plan source."""
        if isinstance(self.source, CandidateTrialSource):
            return self.source.facts.execution
        return self.admission.get("execution")

    def _delivery_scope(self, rows):
        source = self.source
        if isinstance(source, CandidateTrialSource):
            facts, settings = source.facts, source.settings
            # Every selected ref is an archived batch's (``AdmissionBaseline``). The delivery comparison and the
            # unplanned list keep the archive's ref order, the order these batches' refs were created.
            selected = {ref: facts.related("Batches", facts.batch_id(ref)) for ref in settings["batch_refs"]}
            batches = {ref: selected[ref] for (kind, _), ref in facts.entity_refs.items() if kind == "batch" and ref in selected}
            operations = facts.tables["BatchOperations"].values()
            deferred = material_deferred_ids(source.document["dispositions"].values(), settings)
            deferred_issues = []
        else:
            batches = {row["original"]["batch_ref"]: row["original"]["batch"] for row in rows}
            operations = self.admission_operations.values()
            # 正式计划来源在创建试调时就记下了原计划的待料工序编号与缺口。
            document = source.document
            deferred, deferred_issues = set(document["deferred_operation_ids"]), document["deferred_operation_issues"]
            selected = {batch["batch_id"] for batch in batches.values()}
            pending = {operation["batch_id"] for operation in operations if operation["id"] in deferred} - selected
            if pending:
                batch_rows = index_rows(self.tables["Batches"], "batch_id", on_corrupt=invalid_trial_snapshot)
                entity_refs = entity_ref_rows(self.tables["WorkbenchEntityRefs"], on_corrupt=invalid_trial_snapshot)
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
        if isinstance(self.source, CandidateTrialSource):
            operations, refs = self.source.facts.tables["BatchOperations"], self.source.facts.operation_refs
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
                    self.unarranged[ref] = {
                        "operation": op,
                        "batch_ref": batch_ref,
                        "batch": batch,
                        "arranged": False,
                        "deferred": op["id"] in self.deferred,
                    }

    def contexts(self, rows):
        """Bind one stage's rows and every member's source-time execution; arranged rows come first."""
        execution = self.source_execution
        if not isinstance(execution, dict):
            invalid_trial_snapshot()
        result = {
            row["operation_ref"]: {
                "operation": row["original"]["operation"],
                "batch_ref": row["original"]["batch_ref"],
                "batch": row["original"]["batch"],
                "row": row,
                "arranged": True,
                "deferred": row["original"]["operation"]["id"] in self.deferred,
                "execution": row["original"]["execution"],
            }
            for row in rows
        }
        for ref, member in self.unarranged.items():
            if ref not in execution:
                invalid_trial_snapshot()
            result[ref] = dict(member, execution=execution[ref])
        if isinstance(self.source, CandidateTrialSource):
            dispositions = self.source.document.get("dispositions")
            if not isinstance(dispositions, dict):
                invalid_trial_snapshot()
            # 候选来源保存了所选批次全部工序的处置；正式计划来源没有处置。
            for ref, context in result.items():
                if ref not in dispositions:
                    invalid_trial_snapshot()
                context["disposition"] = dispositions[ref]
        return result

"""Saved condition facts with separate trial work and environment provenance."""

from functools import cached_property
from typing import Any, Callable, Dict, List, Union

from core.services.workbench.facts.archived_calendar import CALENDAR_TABLES, ArchivedCalendar
from core.services.workbench.facts.candidate_facts import entity_ref_rows
from core.services.workbench.facts.trial_origin import CandidateTrialSource

from .packets import RunPacket, TrialPacket, UnavailablePacket

# Where each kind of source saved its facts, for the paths a projection reports.
_ORIGINS = {
    "run": {
        "environment": "capture.facts",
        "original": "capture.facts",
        "input": "capture.input",
        "execution": "capture.execution",
        "tasks": "raw_tasks",
    },
    "trial": {
        "environment": "head.admission.facts",
        "input": "head.admission.input",
        "original": "head.admission.source.capture.facts",
        "execution": "head.admission.execution",
        "tasks": "rows",
        "saved": "saved",
    },
    "empty": {},
}


def _table_paths(rows, key, prefix):
    return {row[key]: f"{prefix}[{index}]" for index, row in enumerate(rows)}


def _join_path(prefix, path):
    return prefix + (("" if path.startswith("[") else ".") + path if path else "")


class ConditionSource:
    """Normalize one verified packet without reading current production facts.

    ``operations`` and ``batches`` are permanent-reference indexes. ``execution``
    is the saved operation-reference index; empty collections retain real zero.
    Trial environment tables always belong to the draft admission. Its business work stays
    in ``rows.original`` or the source capture for saved unplanned operations. An unavailable
    source keeps only its kind, identity and issue; no reader reads its saved facts.
    """

    def __init__(self, packet: Union[UnavailablePacket, RunPacket, TrialPacket]):
        self.kind, self.ref, self.entry_ref = packet.kind, packet.ref, packet.entry_ref
        self.issue = packet.source_issue if isinstance(packet, UnavailablePacket) else None
        self.available = self.issue is None
        # Every available source records its input, execution and baseline.
        self.input: Dict[str, Any]
        self.execution: Dict[str, Any]
        self.baseline: Dict[str, Any]
        self.saved: Dict[str, Any]  # trial sources only: the saved draft or scenario snapshot
        self.artifact = self.raw_tasks = self.trial_rows = None
        self.origin = self.trial_contexts = None
        self.operations, self.batches, self.entity_refs = {}, {}, {}
        self.original_entity_refs = {}
        self.refs_by_op_id = {}
        self._input_paths = {}
        self._operation_paths, self._batch_paths = {}, {}
        # An unavailable source keeps its kind's paths; only the empty side has none.
        self._origins = dict(_ORIGINS[self.kind])
        # Every available source binds, once, where its tables are read: its environment tables, and the tables its
        # original work relations were saved in (the same ones except for a trial based on a run candidate).
        self._environment_tables: Callable[[str], List[Dict[str, Any]]]
        self._original_tables: Callable[[str], List[Dict[str, Any]]]
        self._source_cache = {}
        if isinstance(packet, RunPacket):
            self._run(packet)
        elif isinstance(packet, TrialPacket):
            self._trial(packet)

    def _run(self, packet: RunPacket):
        facts, capture = packet.facts, packet.capture
        candidate = packet.candidate
        self.input = capture["input"]
        self.execution, self.baseline = facts.execution, capture["baseline"]
        self.artifact = candidate["artifact"] if candidate is not None else None
        self.raw_tasks = packet.raw_tasks
        self.entity_refs = self.original_entity_refs = facts.entity_refs
        self.refs_by_op_id = facts.operation_refs
        self._environment_tables = self._original_tables = facts.table
        self._work_indexes(
            facts.tables["BatchOperations"],
            facts.tables["Batches"],
            facts.operations,
            self._origins["original"],
        )
        self._input_paths = {key: "capture.input." + key for key in self.input}

    def _work_indexes(self, operations, batches, operation_refs, prefix):
        op_paths = _table_paths(operations.values(), "id", prefix + ".tables.BatchOperations")
        batch_paths = _table_paths(batches.values(), "batch_id", prefix + ".tables.Batches")
        for ref, key in operation_refs.items():
            self.operations[ref], self._operation_paths[ref] = operations[key], op_paths[key]
        for (kind, key), ref in self.entity_refs.items():
            if kind == "batch":
                self.batches[ref], self._batch_paths[ref] = batches[key], batch_paths[key]

    def _trial(self, packet: TrialPacket):
        self.saved, self.trial_rows = packet.saved, packet.rows
        admission = packet.head["admission"]
        self.execution, self.baseline = admission["execution"], admission["baseline"]
        self._environment_tables = packet.origin.tables.__getitem__
        self.entity_refs = entity_ref_rows(self.table("WorkbenchEntityRefs"))
        for index, row in enumerate(self.trial_rows):
            original, ref = row["original"], row["operation_ref"]
            self.operations[ref] = original["operation"]
            self._operation_paths[ref] = f"rows[{index}].original.operation"
            batch_ref = original["batch_ref"]
            if batch_ref not in self.batches:
                self.batches[batch_ref] = original["batch"]
                self._batch_paths[batch_ref] = f"rows[{index}].original.batch"
        self._trial_unplanned(packet.origin)
        self._trial_input(packet.origin.source)

    def _trial_unplanned(self, origin):
        source = origin.source
        if isinstance(source, CandidateTrialSource):
            facts = source.facts
            op_rows = facts.tables["BatchOperations"].values()
            batch_rows = facts.tables["Batches"].values()
            entity_refs = facts.entity_refs
            prefix = "head.admission.source.capture.facts"
            self._original_tables = facts.table
        else:
            op_rows, batch_rows = self.table("BatchOperations"), self.table("Batches")
            entity_refs = self.entity_refs
            prefix = self._origins["environment"]
            self._original_tables = self._environment_tables
        self.origin = origin
        self.original_entity_refs = entity_refs
        self.refs_by_op_id = origin.admission_refs_by_op_id
        self._origins["original"] = prefix
        op_paths = _table_paths(op_rows, "id", prefix + ".tables.BatchOperations")
        batch_paths = _table_paths(batch_rows, "batch_id", prefix + ".tables.Batches")
        self.trial_contexts = origin.contexts(self.trial_rows)
        for ref, member in origin.unarranged.items():
            operation, batch_ref, batch = member["operation"], member["batch_ref"], member["batch"]
            self.operations[ref], self._operation_paths[ref] = operation, op_paths[operation["id"]]
            if batch_ref not in self.batches:
                self.batches[batch_ref], self._batch_paths[batch_ref] = batch, batch_paths[batch["batch_id"]]

    def _trial_input(self, source):
        # The trial's own input names only its base and view scope; its run settings are the source's.
        self.input = source.settings
        prefix = "head.admission.source." + source.settings_path + "."
        self._input_paths = {key: prefix + key for key in self.input}

    @cached_property
    def calendar(self):
        return ArchivedCalendar({name: self.table(name) for name in CALENDAR_TABLES}, source_ref=self.ref)

    def table(self, name):
        """One admitted archive table, decoded once."""
        return self._environment_tables(name)

    def original_table(self, name):
        """Read original work relations without replacing trial environment facts."""
        return self._original_tables(name)

    def input_path(self, key):
        """The saved field path of one recorded input."""
        return self._input_paths[key]

    def source(self, path, origin="environment"):
        """Locate saved fields, including original work indexed by permanent ref."""
        key = (path, origin)
        cached = self._source_cache.get(key)
        if cached is not None:
            return cached
        if self.kind == "empty":
            # 没有选中历史条目的一侧没有保存来源可指。
            result = {"kind": self.kind, "ref": None, "path": None}
            self._source_cache[key] = result
            return result
        if origin == "input" and path in self._input_paths:
            saved_path = self._input_paths[path]
        elif origin == "original" and path.startswith(("operations.", "batches.")):
            kind, ref, *tail = path.split(".")
            paths = self._operation_paths if kind == "operations" else self._batch_paths
            saved_path = paths.get(ref)
            if saved_path is None:
                saved_path = _join_path(self._origins["original"], path)
            elif tail:
                saved_path += "." + ".".join(tail)
        elif path.startswith(("capture.", "candidate.", "receipt.", "head.", "rows[", "saved.")):
            saved_path = path
        else:
            saved_path = _join_path(self._origins[origin], path)
        result = {"kind": self.kind, "ref": self.ref, "path": saved_path}
        self._source_cache[key] = result
        return result

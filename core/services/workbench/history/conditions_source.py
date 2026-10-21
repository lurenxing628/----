"""Saved condition facts with separate trial work and environment provenance."""

from core.models.workbench_run_candidate import reference
from core.services.workbench.facts.archived_calendar import ArchivedCalendar
from core.services.workbench.facts.candidate_facts import GenerationFacts, _index
from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.trial_origin import operation_contexts


def _entity_refs(rows):
    result = {}
    for row in rows or []:
        if row.get("active") != 1:
            continue
        key = (row.get("kind"), row.get("entity_key"))
        if any(type(value) is not str for value in key) or key in result:
            corrupt()
        result[key] = reference(row.get("ref"), stored=True)
    return result


def _operation_refs(rows):
    result = {}
    for row in rows or []:
        if row.get("kind") != "operation" or row.get("active") != 1:
            continue
        ref, key = reference(row.get("ref"), stored=True), row.get("source_key")
        if type(key) is not str or not key.isdigit() or str(int(key)) != key or ref in result:
            corrupt()
        result[ref] = int(key)
    return result


def _table_paths(rows, key, prefix):
    return {row[key]: f"{prefix}[{index}]" for index, row in enumerate(rows or [])}


def _join_path(prefix, path):
    return prefix + (("" if path.startswith("[") else ".") + path if path else "")


class ConditionSource:
    """Normalize one verified packet without reading current production facts.

    ``operations`` and ``batches`` are permanent-reference indexes. ``execution``
    is the saved operation-reference index; empty collections retain real zero.
    Trial ``archive`` always belongs to draft admission. Its business work stays
    in ``rows.original`` or the source capture for saved unplanned operations.
    """

    def __init__(self, packet):
        self.kind, self.ref, self.entry_ref = packet["kind"], packet["ref"], packet["entry_ref"]
        self.issue = packet.get("source_issue")
        self.available = self.kind != "legacy"
        self.archive = self.input = self.execution = self.baseline = None
        self.artifact = self.raw_tasks = self.trial_rows = self.saved = self.calendar = None
        self.original_archive = self._original_calendar = None
        self.operations, self.batches, self.entity_refs = {}, {}, {}
        self.original_entity_refs = {}
        self._input_paths = {}
        self._operation_paths, self._batch_paths, self._origins = {}, {}, {}
        if self.kind == "run":
            self._origins = {"environment": "capture.facts_text", "original": "capture.facts_text",
                             "input": "capture.input", "execution": "capture.execution", "tasks": "raw_tasks"}
            if self._missing_source(packet, ("capture", "facts")):
                return
            self._run(packet)
        elif self.kind == "trial":
            self._origins = {"environment": "head.admission.facts", "input": "head.admission.input",
                             "original": "head.admission.source.capture.facts_text",
                             "execution": "head.admission.execution", "tasks": "rows", "saved": "saved"}
            if self._missing_source(packet, ("head", "saved")):
                return
            self._trial(packet)
        elif self.kind == "legacy":
            self.saved = packet.get("parsed_summary")
            self._origins["environment"] = "parsed_summary"
        else:
            raise ValueError("Unknown saved condition source")

    def _missing_source(self, packet, required):
        if self.issue is None and all(packet.get(key) is not None for key in required):
            return False
        self.available = False
        if self.issue is None:
            self.issue = {"code": "source_missing", "message": "这份历史记录的保存来源缺失，生产条件未知。"}
        return True

    def _run(self, packet):
        facts, capture = packet["facts"], packet["capture"]
        candidate = packet["candidate"]
        self.archive, self.input = facts.archive, capture["input"]
        self.execution, self.baseline = facts.execution, capture["baseline"]
        self.artifact = candidate["artifact"] if candidate is not None else None
        self.raw_tasks = packet["raw_tasks"]
        self.entity_refs = self.original_entity_refs = facts.entity_refs
        self.calendar = ArchivedCalendar(self.archive, source_ref=self.ref, facts=facts)
        self.original_archive, self._original_calendar = self.archive, self.calendar
        self._work_indexes(facts.tables["BatchOperations"], facts.tables["Batches"], facts.operations,
                           self._origins["original"])
        self._input_paths = {key: "capture.input." + key for key in self.input}

    def _work_indexes(self, operations, batches, operation_refs, prefix):
        op_paths = _table_paths(operations.values(), "id", prefix + ".tables.BatchOperations")
        batch_paths = _table_paths(batches.values(), "batch_id", prefix + ".tables.Batches")
        for ref, key in operation_refs.items():
            if key in operations:
                self.operations[ref], self._operation_paths[ref] = operations[key], op_paths[key]
        for (kind, key), ref in self.entity_refs.items():
            if kind == "batch" and key in batches:
                self.batches[ref], self._batch_paths[ref] = batches[key], batch_paths[key]

    def _trial(self, packet):
        self.saved, self.trial_rows = packet["saved"], packet["rows"]
        admission = packet["head"]["admission"]
        self.archive, self.execution, self.baseline = admission["facts"], admission["execution"], admission["baseline"]
        self.calendar = ArchivedCalendar(self.archive, source_ref=self.ref)
        self.entity_refs = _entity_refs(self.table("WorkbenchEntityRefs"))
        for index, row in enumerate(self.trial_rows):
            original, ref = row["original"], row["operation_ref"]
            self.operations[ref] = original["operation"]
            self._operation_paths[ref] = f"rows[{index}].original.operation"
            batch_ref = original["batch_ref"]
            if batch_ref not in self.batches:
                self.batches[batch_ref] = original["batch"]
                self._batch_paths[batch_ref] = f"rows[{index}].original.batch"
        self._trial_unplanned(admission)
        self._trial_input(admission, self.saved)

    def _trial_unplanned(self, admission):
        source = admission["source"]
        capture = source.get("capture")
        facts = None
        if capture is not None and type(capture) is not dict:
            corrupt()
        if capture is not None and capture.get("facts_text") is not None:
            facts = GenerationFacts(capture)
            self.original_archive = facts.archive
            self._original_calendar = ArchivedCalendar(self.original_archive, source_ref=self.ref, facts=facts)
            operations, batches, refs = facts.tables["BatchOperations"], facts.tables["Batches"], facts.operations
            entity_refs = facts.entity_refs
            prefix = "head.admission.source.capture.facts_text"
        else:
            self.original_archive, self._original_calendar = self.archive, self.calendar
            operations, batches = _index(self.table("BatchOperations"), "id"), _index(self.table("Batches"), "batch_id")
            refs, entity_refs = _operation_refs(self.table("WorkbenchPlanSourceRefs")), self.entity_refs
            prefix = self._origins["environment"]
        self.original_entity_refs = entity_refs
        self._origins["original"] = prefix
        op_paths = _table_paths(operations.values(), "id", prefix + ".tables.BatchOperations")
        batch_paths = _table_paths(batches.values(), "batch_id", prefix + ".tables.Batches")
        for ref in operation_contexts(self.trial_rows, admission, facts):
            key = refs.get(ref)
            if key not in operations or ref in self.operations:
                continue
            operation = operations[key]
            self.operations[ref], self._operation_paths[ref] = operation, op_paths[key]
            batch_id = operation.get("batch_id")
            batch_ref = entity_refs.get(("batch", batch_id))
            if batch_ref is not None and batch_id in batches and batch_ref not in self.batches:
                self.batches[batch_ref], self._batch_paths[batch_ref] = batches[batch_id], batch_paths[batch_id]

    def _trial_input(self, admission, saved):
        source = admission["source"]
        self.input = {}
        inputs = ((admission["input"], "head.admission.input"),
                  (source.get("material_policy"), "head.admission.source.material_policy"),
                  ((source.get("capture") or {}).get("input"), "head.admission.source.capture.input"))
        for values, prefix in inputs:
            if values is None:
                continue
            if type(values) is not dict:
                corrupt()
            for key, value in values.items():
                self.input[key], self._input_paths[key] = value, prefix + "." + key
        date_inputs = (inputs[0], inputs[2], inputs[1])
        for key, field, boundary in (("start_date", "start", min), ("end_date", "end", max)):
            for values, prefix in date_inputs:
                if values is not None and key in values:
                    self.input[key], self._input_paths[key] = values[key], prefix + "." + key
                    break
            else:
                tasks = saved.get("tasks")
                if tasks:
                    index, task = boundary(enumerate(tasks), key=lambda item: item[1][field])
                    value = task[field]
                    self.input[key] = value[:10] if type(value) is str else value
                    self._input_paths[key] = f"saved.tasks[{index}].{field}"

    def table(self, name):
        """Keep saved empty tables distinct from missing tables and columns."""
        return self.calendar.table(name) if self.calendar is not None else None

    def original_table(self, name):
        """Read original work relations without replacing trial environment facts."""
        return self._original_calendar.table(name) if self._original_calendar is not None else None

    def input_path(self, key):
        """Return the saved field path, or None when that input was absent."""
        return self._input_paths.get(key)

    def source(self, path, origin="environment"):
        """Locate saved fields, including original work indexed by permanent ref."""
        if self.kind == "legacy":
            saved_path = path if path.startswith("parsed_summary") else _join_path("parsed_summary", path)
        elif origin == "input" and path in self._input_paths:
            saved_path = self._input_paths[path]
        elif origin == "original" and path.startswith(("operations.", "batches.")):
            kind, ref, *tail = path.split(".")
            paths = self._operation_paths if kind == "operations" else self._batch_paths
            saved_path = paths.get(ref)
            if saved_path is None:
                saved_path = _join_path(self._origins["original"], path)
            elif tail:
                saved_path += "." + ".".join(tail)
        elif path.startswith(("capture.", "candidate.", "receipt.", "head.", "rows[", "saved.", "parsed_summary")):
            saved_path = path
        else:
            prefix = self._origins.get(origin)
            if prefix is None:
                raise ValueError("Unknown saved condition origin")
            saved_path = _join_path(prefix, path)
        return {"kind": self.kind, "ref": self.ref, "path": saved_path}

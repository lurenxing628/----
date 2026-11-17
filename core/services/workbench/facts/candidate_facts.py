"""Interpret acceptance-time facts only; current replacement entities are irrelevant."""

import base64
from collections import defaultdict
from collections.abc import Mapping
from functools import cached_property
from typing import Any, Callable, List, NoReturn, Tuple

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_candidate import reference

from .candidate_values import corrupt, gap, is_blob_metadata, number, text
from .delivery_projection import parse_stored_due_date
from .production_capture import ArchivedTables, validate_production_archive

# The key column each archived table besides ``BatchOperations`` is read by.
TABLE_KEYS = {"Batches": "batch_id", "Parts": "part_no", "Machines": "machine_id",
              "Operators": "operator_id", "Suppliers": "supplier_id", "OpTypes": "op_type_id"}


def _stored_reference(value, on_corrupt: Callable[[], NoReturn]) -> str:
    try:
        return reference(value, stored=True)
    except WorkbenchCommandRejected:
        if on_corrupt is corrupt:
            raise
        on_corrupt()


def index_rows(rows, key, *, on_corrupt: Callable[[], NoReturn] = corrupt):
    if type(rows) is not list:
        on_corrupt()
    result = {}
    for row in rows:
        if type(row) is not dict:
            on_corrupt()
        value = row.get(key)
        if type(value) not in (int, str) or value in result:
            on_corrupt()
        result[value] = row
    return result


def batch_operation_rows(rows, *, on_corrupt: Callable[[], NoReturn] = corrupt):
    indexed = index_rows(rows, "id", on_corrupt=on_corrupt)
    for op_id, row in indexed.items():
        if type(op_id) is not int or type(row.get("batch_id")) is not str:
            on_corrupt()
    return indexed


def entity_ref_rows(rows, *, on_corrupt: Callable[[], NoReturn] = corrupt):
    if type(rows) is not list:
        on_corrupt()
    result = {}
    for row in rows:
        if type(row) is not dict:
            on_corrupt()
        if row.get("active") != 1:
            continue
        key = (row.get("kind"), row.get("entity_key"))
        if any(type(item) is not str for item in key) or key in result:
            on_corrupt()
        result[key] = _stored_reference(row.get("ref"), on_corrupt)
    return result


def operation_ref_rows(rows, *, on_corrupt: Callable[[], NoReturn] = corrupt):
    if type(rows) is not list:
        on_corrupt()
    result = {}
    for row in rows:
        if type(row) is not dict:
            on_corrupt()
        # 来源编号表只有工序一种、ref 是主键（建表约束与归档准入），只按是否仍有效筛选。
        if row.get("active") != 1:
            continue
        ref, key = _stored_reference(row.get("ref"), on_corrupt), row.get("source_key")
        if type(key) is not str or not key.isascii() or not key.isdigit() or str(int(key)) != key:
            on_corrupt()
        result[ref] = int(key)
    return result


def operation_refs_by_id(operations, *, on_corrupt: Callable[[], NoReturn] = corrupt):
    result = {}
    for ref, op_id in operations.items():
        if op_id in result:
            on_corrupt()
        result[op_id] = ref
    return result


def operation_type_identity(refs, op_types, type_id):
    """An operation type's permanent ref and name in one set of facts (``refs`` keyed ``("op_type", id)``, ``op_types``
    by id): every reader of an operation's type takes it from the operation through here. An operation without a type
    (``BatchOperations.op_type_id`` is nullable) has neither. Any other type is registered: ``OpTypes`` is archived
    whole with every active permanent ref, a type in use cannot be deleted and every type row keeps one active ref
    (``wb_ref_op_type_*``); a missing one is a corrupt archive."""
    if type_id is None:
        return None, None
    return refs[("op_type", type_id)], op_types[type_id]["name"]


def require_arranged_type(operation):
    """An operation a saved arrangement scheduled has a type: preflight blocks an untyped one (``op_type_missing``)
    and a batch operation's type is fixed from its template copy, so an arranged one without a type is corrupt."""
    if operation["op_type_id"] is None:
        corrupt()


def _raw_sql_value(value):
    if isinstance(value, Mapping) and set(value) == {"$sqlite_blob"} and type(value["$sqlite_blob"]) is str:
        return base64.b64decode(value["$sqlite_blob"], validate=True)
    return value


# The archived table of each resource kind an operation or arrangement assigns.
RESOURCE_TABLES = {"machine": "Machines", "operator": "Operators", "supplier": "Suppliers"}


def _archived_resource(facts: "GenerationFacts", kind, key):
    """An operation's assigned resource (``BatchOperations`` keeps it nullable) as its ref and stored label."""
    if key is None:
        return None, None
    return facts.entity_ref(kind, key), text(facts.related(RESOURCE_TABLES[kind], key)["name"], kind + ".label", [])


def build_run_archive_rows(run_ref: str, facts: "GenerationFacts") -> Tuple[List[Tuple[Any, ...]], List[Tuple[Any, ...]]]:
    """Build structured WorkbenchRunBatches and WorkbenchRunOperations tuples from an archive just captured."""
    batches: List[Tuple[Any, ...]] = []
    for batch_id in sorted(facts.tables["Batches"]):
        batch = facts.tables["Batches"][batch_id]
        part_no = batch["part_no"]
        batches.append((
            run_ref, facts.entity_ref("batch", batch_id), batch_id, part_no, facts.entity_ref("part", part_no),
            batch["part_name"], batch["quantity"], _raw_sql_value(batch["due_date"]), batch["priority"],
            batch["ready_status"], batch["ready_date"], batch["status"],
        ))
    operations: List[Tuple[Any, ...]] = []
    for op_id in sorted(facts.tables["BatchOperations"]):
        op = facts.tables["BatchOperations"][op_id]
        batch_id = op["batch_id"]
        op_type_ref, op_type_label = operation_type_identity(facts.entity_refs, facts.tables["OpTypes"], op["op_type_id"])
        operations.append((
            run_ref, facts.operation_refs[op_id], op_id, op["op_code"], batch_id, facts.entity_ref("batch", batch_id),
            op["piece_id"], op["seq"], op["op_type_id"], op["op_type_name"], op_type_ref, op_type_label,
            op["source"], op["setup_hours"], op["unit_hours"], op["ext_days"],
            op["machine_id"], *_archived_resource(facts, "machine", op["machine_id"]),
            op["operator_id"], *_archived_resource(facts, "operator", op["operator_id"]),
            op["supplier_id"], *_archived_resource(facts, "supplier", op["supplier_id"]),
            op["status"],
        ))
    return batches, operations


def admit_generation_facts(capture) -> "GenerationFacts":
    """The one admission of a stored generation capture, at its storage boundary: the production archive
    (``validate_production_archive``) and the permanent refs its execution rows are keyed by. An archive this
    process has just built is indexed as it is (``GenerationFacts``)."""
    try:
        validate_production_archive(capture["facts"])
    except ValueError:
        corrupt()
    facts = GenerationFacts(capture)
    for ref in facts.execution:
        reference(ref, stored=True)
    return facts


class GenerationFacts:
    def __init__(self, capture):
        """Index an admitted compact production archive's original tables and the capture's execution rows."""
        facts = capture["facts"]
        self.archive = facts
        self._tables = ArchivedTables(facts)
        self.tables = {
            "BatchOperations": batch_operation_rows(self.table("BatchOperations")),
            **{name: index_rows(self.table(name), key) for name, key in TABLE_KEYS.items()},
        }
        self.entity_refs = entity_ref_rows(self.table("WorkbenchEntityRefs"))
        self.operations = operation_ref_rows(self.table("WorkbenchPlanSourceRefs"))
        self.execution = index_rows(capture["execution"], "operation_ref")
        self._operation_labels = {}

    def table(self, name):
        """An immutable saved table, decoded once for all consumers of this source."""
        return self._tables[name]

    @cached_property
    def operations_by_batch(self):
        result = defaultdict(list)
        for operation in self.tables["BatchOperations"].values():
            result[operation["batch_id"]].append(dict(operation, op_id=operation["id"]))
        return dict(result)

    @cached_property
    def batch_ids_by_ref(self):
        return {ref: key for (kind, key), ref in self.entity_refs.items() if kind == "batch"}

    @cached_property
    def operation_refs(self):
        return operation_refs_by_id(self.operations)

    # The archive's relations, read only through these: ``ProductionFactsCapture.scoped_archive`` keeps, in one
    # transaction, every operation of its batches with the batches and parts they belong to (foreign keys), the
    # resource and type tables whole, the active ref of every kept operation (``wb_plan_operation_*``) and of every
    # kept row (``wb_ref_*`` keeps one per row). A relation missing from a stored archive is a corrupt archive.

    def operation(self, ref, op_id=None):
        """The archived operation ``ref`` names; a saved arrangement's ``op_id`` must be the one ``ref`` names."""
        key = self.operations.get(ref)
        if key is None or op_id is not None and op_id != key:
            corrupt()
        return self.related("BatchOperations", key)

    def related(self, name, key):
        """The archived ``name`` row an archived row refers to by ``key``."""
        row = self.tables[name].get(key)
        if row is None:
            corrupt()
        return row

    def entity_ref(self, kind, key):
        """The active permanent ref of an archived row."""
        ref = self.entity_refs.get((kind, key))
        if ref is None:
            corrupt()
        return ref

    def batch_id(self, ref):
        """The archived batch a permanent batch ref names."""
        key = self.batch_ids_by_ref.get(ref)
        if key is None:
            corrupt()
        return key

    def operation_batch_ref(self, ref):
        return self.entity_ref("batch", self.operation(ref)["batch_id"])

    def base_operation_labels(self, ref, op):
        """This archived operation's labels, built once per capture."""
        if ref not in self._operation_labels:
            self._operation_labels[ref] = self._operation_labels_from(ref, op)
        return self._operation_labels[ref]

    def _operation_labels_from(self, ref, op):
        gaps = []
        batch = self.related("Batches", op["batch_id"])
        part = self.related("Parts", batch["part_no"])
        piece_id = op["piece_id"]
        if piece_id is not None:
            piece_id = text(piece_id, "piece_id", gaps)
        execution = self._execution_at_generation(ref, gaps)
        quantity = execution["target_quantity"] if execution is not None else None
        if (any(item["field"] == "piece_id" for item in gaps) or execution is None
                or execution["target_basis"] != ("piece" if piece_id is not None else "batch")):
            quantity = None
            gaps.append(gap("quantity", "source_missing"))
        result = {"operation_ref": ref, "batch_ref": self.entity_ref("batch", op["batch_id"]),
                  "batch_label": text(batch["batch_id"], "batch_label", gaps),
                  "part_label": text(part["part_name"], "part_label", gaps),
                  "sequence": number(op["seq"], "sequence", gaps, integer=True),
                  "process_label": text(op["op_type_name"], "process_label", gaps),
                  "piece_id": piece_id, "quantity": quantity,
                  "batch_quantity": batch["quantity"],
                  **_stored_date(batch["due_date"], "due_date", gaps),
                  "execution_at_generation": execution, "data_gaps": gaps}
        result.update(self.operation_type_labels(op["op_type_id"]))
        return result

    def _execution_at_generation(self, ref, gaps):
        row = self.execution.get(ref)
        if row is None:
            gaps.append(gap("execution_at_generation", "source_missing"))
            return None
        values = {key: number(row.get(key), "execution_at_generation." + key, gaps, integer=True)
                  for key in ("target_quantity", "known_completed_quantity", "remaining_quantity")}
        domains = {"execution_state": ("complete", "partial", "started", "unreported"),
                   "data_quality": ("invalid", "incomplete", "complete"), "target_basis": ("piece", "batch")}
        for key, allowed in domains.items():
            value = row.get(key)
            values[key] = value if type(value) is str and value in allowed else None
            if values[key] is None:
                gaps.append(gap("execution_at_generation." + key, "invalid_stored_value"))
        return values

    def operation_type_labels(self, type_id):
        """An archived operation's type as task views and adoption snapshots carry it (``operation_type_identity``)."""
        ref, label = operation_type_identity(self.entity_refs, self.tables["OpTypes"], type_id)
        return {"process_type_ref": ref, "process_type_label": label}


def _stored_date(value, field, gaps):
    due_date, _deadline, due_state, due_issue = parse_stored_due_date(value)
    if due_issue is not None:
        if due_issue == "due_date_missing":
            code = "not_recorded"
        elif is_blob_metadata(value):
            code = "blob_metadata"
        else:
            code = "invalid_stored_value"
        gaps.append(gap(field, code))
    return {"due_date": due_date, "due_state": due_state, "due_issue": due_issue}

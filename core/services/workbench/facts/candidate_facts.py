"""Interpret acceptance-time facts only; current replacement entities are irrelevant."""

from collections import defaultdict
from collections.abc import Mapping
from functools import cached_property
from typing import Any, Callable, Dict, List, NoReturn

from core.infrastructure.schema_structure import declared_table_columns
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_candidate import reference

from .candidate_values import corrupt, gap, is_blob_metadata, number, stored_json, text
from .delivery_projection import parse_stored_due_date
from .production_capture import (
    archived_table_valid,
    validate_production_archive,
)

_TABLES = {"Batches": "batch_id", "Parts": "part_no", "Machines": "machine_id",
           "Operators": "operator_id", "Suppliers": "supplier_id", "OpTypes": "op_type_id"}


def _stored_reference(value, on_corrupt: Callable[[], NoReturn]) -> str:
    try:
        return reference(value, stored=True)
    except WorkbenchCommandRejected:
        if on_corrupt is corrupt:
            raise
        on_corrupt()


def archived_rows(archive, name) -> List[Dict[str, Any]]:
    """One table of an admitted archive, each row named by the archive's own column order."""
    columns = archive["columns"][name]
    return [dict(zip(columns, row)) if type(row) is list else dict(row) for row in archive["tables"][name]]


def archived_table(facts, name) -> List[Dict[str, Any]]:
    """Admit and decode one table of a saved partial archive; a table it does not record is corrupt, never empty."""
    if not isinstance(facts, Mapping):
        corrupt()
    schema, tables, columns_map = facts.get("schema"), facts.get("tables"), facts.get("columns")
    if type(schema) is not list or type(tables) is not dict or not isinstance(columns_map, Mapping) or name not in tables:
        corrupt()
    ddl = [row[3] for row in schema
           if type(row) is list and len(row) == 4 and row[0] == "table" and row[1] == name and row[2] == name]
    if len(ddl) != 1 or not archived_table_valid(columns_map.get(name), tables[name]):
        corrupt()
    try:
        declared_cols = declared_table_columns(name, ddl[0])
    except ValueError:
        corrupt()
    if tuple(columns_map[name]) != declared_cols:
        corrupt()
    return archived_rows(facts, name)


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
    if rows is not None and type(rows) is not list:
        on_corrupt()
    result = {}
    for row in rows or []:
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
        if row.get("kind") != "operation" or row.get("active") != 1:
            continue
        ref, key = _stored_reference(row.get("ref"), on_corrupt), row.get("source_key")
        if type(key) is not str or not key.isascii() or not key.isdigit() or str(int(key)) != key or ref in result:
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


class GenerationFacts:
    def __init__(self, capture):
        """``capture["facts"]`` is an archive this process built or already admitted; a stored capture
        carries only ``facts_text``, decoded and admitted here at its first entry."""
        facts = capture.get("facts")
        if facts is None:
            facts = stored_json(capture["facts_text"])
            try:
                validate_production_archive(facts)
            except ValueError:
                corrupt()
        self.archive = facts
        self._decoded_tables = {}
        self.tables = {"BatchOperations": batch_operation_rows(self.table("BatchOperations")),
                       **{name: index_rows(self.table(name), key) for name, key in _TABLES.items()}}
        self.entity_refs = entity_ref_rows(self.table("WorkbenchEntityRefs"))
        self.operations = operation_ref_rows(self.table("WorkbenchPlanSourceRefs"))
        self.execution = index_rows(capture["execution"], "operation_ref")
        self._operation_labels = {}
        for ref in self.execution:
            reference(ref, stored=True)

    def table(self, name):
        """Decode an immutable saved table once for all consumers of this source.

        An archive recorded under a schema without this table is corrupt for its reader, never empty.
        """
        if name not in self._decoded_tables:
            if name not in self.archive["tables"]:
                corrupt()
            self._decoded_tables[name] = archived_rows(self.archive, name)
        return self._decoded_tables[name]

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

    def operation_batch_ref(self, ref):
        op_id = self.operations.get(ref)
        op = self.tables["BatchOperations"].get(op_id) if op_id is not None else None
        return self.entity_refs.get(("batch", op["batch_id"])) if op is not None else None

    def operation(self, ref, payload, gaps):
        key = self.operations.get(ref)
        if key is None:
            gaps.append(gap("operation", "source_missing"))
            return {}
        if payload is not None and (type(payload.get("op_id")) is not int or payload["op_id"] != key):
            corrupt()
        row = self.tables["BatchOperations"].get(key)
        if row is None:
            gaps.append(gap("operation", "source_missing"))
        return row or {}

    def related(self, name, key, field, gaps):
        if type(key) not in (str, int):
            gaps.append(gap(field, "source_missing"))
            return {}
        row = self.tables[name].get(key)
        if row is None:
            gaps.append(gap(field, "source_missing"))
        return row or {}

    def base_operation_labels(self, ref, op, gaps):
        """This operation's archived labels, built once per capture; the first build records its gaps in ``gaps``."""
        if ref not in self._operation_labels:
            self._operation_labels[ref] = self._operation_labels_from(ref, op, gaps)
        return self._operation_labels[ref]

    def _operation_labels_from(self, ref, op, gaps):
        batch = self.related("Batches", op.get("batch_id"), "batch", gaps)
        part = self.related("Parts", batch.get("part_no"), "part", gaps)
        batch_key = op.get("batch_id")
        batch_ref = self.entity_refs.get(("batch", batch_key)) if type(batch_key) is str else None
        if batch_ref is None:
            gaps.append(gap("batch_ref", "source_missing"))
        piece_id = op.get("piece_id")
        if piece_id is not None or "piece_id" not in op:
            piece_id = text(piece_id, "piece_id", gaps)
        execution = self._execution_at_generation(ref, gaps)
        quantity = execution["target_quantity"] if execution is not None else None
        if (any(item["field"] == "piece_id" for item in gaps) or execution is None
                or execution["target_basis"] != ("piece" if piece_id is not None else "batch")):
            quantity = None
            gaps.append(gap("quantity", "source_missing"))
        result = {"operation_ref": ref, "batch_ref": batch_ref,
                  "batch_label": text(batch.get("batch_id"), "batch_label", gaps),
                  "part_label": text(part.get("part_name"), "part_label", gaps),
                  "sequence": number(op.get("seq"), "sequence", gaps, integer=True),
                  "process_label": text(op.get("op_type_name"), "process_label", gaps),
                  "piece_id": piece_id, "quantity": quantity,
                  "batch_quantity": number(batch.get("quantity"), "batch_quantity", gaps, integer=True),
                  **_stored_date(batch.get("due_date"), "due_date", gaps),
                  "execution_at_generation": execution, "data_gaps": gaps}
        result.update(self.operation_type_labels(op.get("op_type_id")))
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
        ref = self.entity_refs.get(("op_type", type_id)) if type(type_id) is str else None
        label = self.tables["OpTypes"].get(type_id, {}).get("name") if type(type_id) is str else None
        return {"process_type_ref": ref, "process_type_label": label if type(label) is str else None}


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

"""Interpret acceptance-time facts only; current replacement entities are irrelevant."""

from collections import defaultdict
from datetime import date
from functools import cached_property

from core.models.workbench_run_candidate import reference

from .candidate_values import corrupt, gap, number, stored_json, text
from .schema_compat import archived_columns

_TABLES = {"BatchOperations": "id", "Batches": "batch_id", "Parts": "part_no",
           "Machines": "machine_id", "Operators": "operator_id", "Suppliers": "supplier_id", "OpTypes": "op_type_id"}


def archived_table(facts, name):
    schema, tables = facts.get("schema"), facts.get("tables")
    if type(schema) is not list or type(tables) is not dict or type(facts.get("columns", {})) is not dict:
        corrupt()
    if name not in tables:
        return None
    ddl = [row[3] for row in schema if type(row) is list and len(row) == 4 and row[0] == "table" and row[1] == name]
    if len(ddl) != 1 or type(tables[name]) is not list:
        corrupt()
    try:
        columns = archived_columns(facts, name)
    except (ValueError, TypeError, KeyError):
        corrupt()
    if not columns or len(set(columns)) != len(columns):
        corrupt()
    column_set = frozenset(columns)
    result = []
    for row in tables[name]:
        if type(row) is dict:
            if row.keys() != column_set:
                corrupt()
            result.append(dict(row))
        elif type(row) is list and len(row) == len(columns):
            result.append(dict(zip(columns, row)))
        else:
            corrupt()
    return result


def index_rows(rows, key):
    result = {}
    for row in rows or []:
        if type(row) is not dict:
            corrupt()
        value = row.get(key)
        if type(value) not in (int, str) or value in result:
            corrupt()
        result[value] = row
    return result


def entity_ref_rows(rows):
    result = {}
    for row in rows or []:
        if row.get("active") != 1:
            continue
        key = (row.get("kind"), row.get("entity_key"))
        if any(type(item) is not str for item in key) or key in result:
            corrupt()
        result[key] = reference(row.get("ref"), stored=True)
    return result


def operation_ref_rows(rows):
    result = {}
    for row in rows or []:
        if row.get("kind") != "operation" or row.get("active") != 1:
            continue
        ref, key = reference(row.get("ref"), stored=True), row.get("source_key")
        if type(key) is not str or not key.isascii() or not key.isdigit() or str(int(key)) != key or ref in result:
            corrupt()
        result[ref] = int(key)
    return result


class GenerationFacts:
    def __init__(self, capture):
        value = capture["facts_text"]
        facts = stored_json(value)
        self.archive = facts
        self._decoded_tables = {}
        self.tables = {name: index_rows(self.table(name), key) for name, key in _TABLES.items()}
        self.entity_refs = entity_ref_rows(self.table("WorkbenchEntityRefs"))
        self.operations = operation_ref_rows(self.table("WorkbenchPlanSourceRefs"))
        self.execution = index_rows(capture["execution"], "operation_ref")
        self._operation_labels = {}
        for ref in self.execution:
            reference(ref, stored=True)

    def table(self, name):
        """Decode an immutable saved table once for all consumers of this source."""
        if name not in self._decoded_tables:
            self._decoded_tables[name] = archived_table(self.archive, name)
        return self._decoded_tables[name]

    @cached_property
    def operations_by_batch(self):
        result = defaultdict(list)
        for operation in self.tables["BatchOperations"].values():
            if type(operation.get("batch_id")) is not str:
                corrupt()
            result[operation["batch_id"]].append(dict(operation, op_id=operation["id"]))
        return dict(result)

    @cached_property
    def batch_ids_by_ref(self):
        return {ref: key for (kind, key), ref in self.entity_refs.items() if kind == "batch"}

    @cached_property
    def operation_refs(self):
        return {key: ref for ref, key in self.operations.items()}

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
                  "due_date": _stored_date(batch.get("due_date"), "due_date", gaps),
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
    result = text(value, field, gaps)
    if result is not None:
        try:
            if date.fromisoformat(result).isoformat() == result:
                return result
        except ValueError:
            pass
        gaps.append(gap(field, "invalid_stored_value"))
    return None

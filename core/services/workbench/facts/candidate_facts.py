"""Interpret acceptance-time facts only; current replacement entities are irrelevant."""

from collections import defaultdict
from functools import cached_property

from core.models.workbench_run_candidate import reference

from .candidate_values import corrupt, gap, stored_json
from .schema_compat import archived_columns

_TABLES = {"BatchOperations": "id", "Batches": "batch_id", "Parts": "part_no",
           "Machines": "machine_id", "Operators": "operator_id", "Suppliers": "supplier_id", "OpTypes": "op_type_id"}


def _table(facts, name):
    schema, tables = facts.get("schema"), facts.get("tables")
    if type(schema) is not list or type(tables) is not dict:
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
    if not columns:
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


def _index(rows, key):
    result = {}
    for row in rows or []:
        if type(row) is not dict:
            corrupt()
        value = row.get(key)
        if type(value) not in (int, str) or value in result:
            corrupt()
        result[value] = row
    return result


def _entity_refs(facts):
    return _entity_ref_rows(_table(facts, "WorkbenchEntityRefs"))


def _entity_ref_rows(rows):
    result = {}
    for row in rows or []:
        if row.get("active") != 1:
            continue
        key = (row.get("kind"), row.get("entity_key"))
        if any(type(item) is not str for item in key) or key in result:
            corrupt()
        result[key] = reference(row.get("ref"), stored=True)
    return result


def _operation_ref_rows(rows):
    result = {}
    for row in rows or []:
        if row.get("kind") != "operation" or row.get("active") != 1:
            continue
        ref, key = reference(row.get("ref"), stored=True), row.get("source_key")
        if type(key) is not str or not key.isdigit() or str(int(key)) != key or ref in result:
            corrupt()
        result[ref] = int(key)
    return result


class GenerationFacts:
    def __init__(self, capture):
        value = capture["facts_text"]
        facts = stored_json(value)
        self.archive = facts
        self._decoded_tables = {}
        self.tables = {name: _index(self.table(name), key) for name, key in _TABLES.items()}
        self.entity_refs = _entity_ref_rows(self.table("WorkbenchEntityRefs"))
        self.operations = _operation_ref_rows(self.table("WorkbenchPlanSourceRefs"))
        self.execution = _index(capture["execution"], "operation_ref")
        self._operation_labels = {}
        for ref in self.execution:
            reference(ref, stored=True)

    def table(self, name):
        """Decode an immutable saved table once for all consumers of this source."""
        if name not in self._decoded_tables:
            self._decoded_tables[name] = _table(self.archive, name)
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

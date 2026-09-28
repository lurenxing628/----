"""Interpret pre-v33 candidate facts without consulting replacement live templates."""

import re
from typing import Any, Collection, Dict, List, Optional

from core.infrastructure.snapshot_connection import ddl_columns
from core.models.enums import BatchExternalContextOrigin, SourceType
from core.services.scheduler.contracts.external_context import context_problem

_V33_OBJECT = re.compile(
    r"\b(?:BatchExternalContexts|batch_external_context_created|batch_external_context_source_changed)\b", re.I)
_TABLE_FIELDS = (
    ("SchemaVersion", ("id", "version")),
    ("BatchOperations", ("id", "batch_id", "seq", "source")),
    ("Batches", ("batch_id", "part_no")),
    ("PartOperations", ("id", "part_no", "seq", "status", "ext_group_id")),
    ("ExternalGroups", ("group_id", "part_no", "start_seq", "end_seq", "merge_mode", "total_days", "supplier_id")),
    ("WorkbenchEntityRefs", ("ref", "kind", "entity_key", "active")),
)


def _schema(captured):
    if type(captured) is not dict or type(captured.get("schema")) is not list:
        return None
    tables, columns = captured.get("tables"), captured.get("columns", {})
    if type(tables) is not dict or type(columns) is not dict:
        return None
    if any(type(name) is not str or _V33_OBJECT.search(name) for name in tuple(tables) + tuple(columns)):
        return None
    return _catalog_definitions(captured["schema"])


def _catalog_definitions(schema):
    """Validate the complete archived object catalog before using any table DDL."""
    definitions, names = {}, set()
    for row in schema:
        if not _schema_row(row):
            return None
        kind, name, owner, sql = row
        identity = (kind, name.casefold())
        if identity in names or any(_V33_OBJECT.search(value) for value in row if type(value) is str):
            return None
        names.add(identity)
        if kind == "table":
            if owner != name or type(sql) is not str:
                return None
            definitions[name] = sql
    return definitions


def _schema_row(row):
    return (type(row) is list and len(row) == 4
            and all(type(value) is str and value for value in row[:3])
            and row[0] in ("table", "index", "trigger", "view")
            and ((row[0] == "index" and row[3] is None) or (type(row[3]) is str and bool(row[3].strip()))))


def _read_table(captured, definitions, name, required):
    rows, sql = captured["tables"].get(name), definitions.get(name)
    if type(rows) is not list or type(sql) is not str:
        return None
    try:
        columns = ddl_columns(sql, name, restricted=True)
    except ValueError:
        # None is an explicit refusal of compatibility, never an empty successful capture.
        return None
    if not set(required) <= set(columns):
        return None
    if "columns" in captured and captured["columns"].get(name) != columns:
        return None
    if any(type(row) is not list or len(row) != len(columns) for row in rows):
        return None
    return [dict(zip(columns, row)) for row in rows]


def _identity(value, expected):
    return type(value) is expected and (value > 0 if expected is int else bool(value.strip()))


def _index(rows, fields):
    result = {}
    for row in rows:
        if any(not _identity(row[name], expected) for name, expected in fields):
            return None
        key = tuple(row[name] for name, _ in fields)
        if key in result:
            return None
        result[key] = row
    return result


def _references(rows):
    result, used = {}, set()
    for row in rows:
        if type(row["active"]) is not int or row["active"] not in (0, 1):
            return None
        if row["active"] == 0:
            continue
        key = (row["kind"], row["entity_key"])
        ref = row["ref"]
        if (any(type(value) is not str for value in key) or key in result
                or type(ref) is not str or len(ref) != 48 or any(c not in "0123456789abcdef" for c in ref)
                or ref in used):
            return None
        result[key] = ref
        used.add(ref)
    return result


def _context(operation, batches, templates, groups, refs):
    if not _identity(operation["batch_id"], str) or not _identity(operation["seq"], int):
        return None
    batch = batches.get((operation["batch_id"],))
    if batch is None or not _identity(batch["part_no"], str):
        return None
    template = templates.get((batch["part_no"], operation["seq"]))
    if template is None:
        return None
    group_id = template["ext_group_id"]
    if group_id is not None and not _identity(group_id, str):
        return None
    group = groups.get((group_id,)) if group_id is not None else None
    if group_id is not None and group is None:
        return None
    context = {"operation_id": operation["id"], "part_no": batch["part_no"], "sequence": operation["seq"],
               "template_operation_id": template["id"], "template_status": template["status"],
               "template_operation_ref": refs.get(("template_operation", str(template["id"]))),
               "group_id": group_id, "group_ref": refs.get(("template_external_group", group_id)),
               "origin": BatchExternalContextOrigin.ARCHIVE_PRE_V33.value, "captured_at": None}
    for field, source in (("group_part_no", "part_no"), ("start_sequence", "start_seq"),
                          ("end_sequence", "end_seq"), ("merge_mode", "merge_mode"),
                          ("total_days", "total_days"), ("supplier_id", "supplier_id")):
        context[field] = group[source] if group is not None else None
    if context_problem(context, operation_id=operation["id"], part_no=batch["part_no"], sequence=operation["seq"]):
        return None
    return context


def _archived_tables(captured):
    """Decode required facts and prove the archived version predates frozen contexts."""
    definitions = _schema(captured)
    if definitions is None:
        return None
    tables = {}
    for name, required in _TABLE_FIELDS:
        rows = _read_table(captured, definitions, name, required)
        if rows is None:
            return None
        tables[name] = rows
    versions = tables["SchemaVersion"]
    if (len(versions) != 1 or type(versions[0]["id"]) is not int or versions[0]["id"] != 1
            or type(versions[0]["version"]) is not int or not 1 <= versions[0]["version"] <= 32):
        return None
    return tables


def _context_indexes(tables):
    """Build each identity index once, rejecting ambiguous archive bindings."""
    operations = _index(tables["BatchOperations"], (("id", int),))
    batches = _index(tables["Batches"], (("batch_id", str),))
    templates = _index(tables["PartOperations"], (("part_no", str), ("seq", int)))
    template_ids = _index(tables["PartOperations"], (("id", int),))
    groups = _index(tables["ExternalGroups"], (("group_id", str),))
    refs = _references(tables["WorkbenchEntityRefs"])
    if (operations is None or batches is None or templates is None or template_ids is None
            or groups is None or refs is None):
        return None
    return operations, batches, templates, groups, refs


def archived_contexts(captured_facts: Dict[str, Any], operation_ids: Collection[int]) -> Optional[List[Dict[str, Any]]]:
    """Return selected old external contexts, or None when compatibility is unproven.

    The caller must authenticate facts_text first. Only the archive's DDL is parsed,
    in a restricted empty in-memory database; no production connection is accepted.
    An empty list proves a supported old capture has no selected external operations. None
    requires the caller to reject a missing external context, not use live facts.
    """
    tables = _archived_tables(captured_facts)
    if tables is None:
        return None
    indexes = _context_indexes(tables)
    if indexes is None:
        return None
    operations, batches, templates, groups, refs = indexes
    if any(not _identity(value, int) for value in operation_ids):
        return None
    selected = set(operation_ids)
    if not selected <= {key[0] for key in operations}:
        return None
    result = []
    for operation in operations.values():
        if operation["id"] not in selected:
            continue
        if str(operation["source"] or "").strip().lower() != SourceType.EXTERNAL.value:
            return None
        context = _context(operation, batches, templates, groups, refs)
        if context is None:
            return None
        result.append(context)
    return result

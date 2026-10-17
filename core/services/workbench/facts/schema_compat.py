"""Compare the declared v39-v44 representation without rewriting saved facts."""

import base64
from functools import lru_cache

from core.infrastructure.efficiency_indexes_schema import ADDED as EFFICIENCY_INDEXES
from core.infrastructure.schedule_business_roles_schema import objects as business_role_objects
from core.infrastructure.single_pass_indexes_schema import ADDED, REMOVED
from core.infrastructure.snapshot_connection import ddl_columns
from core.infrastructure.workbench_content_schema import CONTENT_TABLES, content_objects
from core.infrastructure.workbench_metadata_schema import canonical_ddl_parts, canonical_sql
from core.infrastructure.workbench_run_read_model_schema import READ_MODEL_TABLES
from core.infrastructure.workbench_run_read_model_schema import objects as read_model_objects
from core.models.content import packed, unpacked


@lru_cache(maxsize=2)
def _definitions(legacy=False):
    return {name: sql for name, sql in content_objects(legacy=legacy).items() if name in CONTENT_TABLES}


@lru_cache(maxsize=256)
def _columns(sql, name):
    current, legacy = _definitions(), _definitions(True)
    known = current.get(name)
    if known is not None and canonical_sql(sql) in (canonical_sql(known), canonical_sql(legacy[name])):
        definition = legacy[name] if canonical_sql(sql) == canonical_sql(legacy[name]) else known
        names = {column.casefold(): column for column in ddl_columns(definition, name)}
        ordered = [names[part.split(" ", 1)[0].casefold()] for part in canonical_ddl_parts(sql)
                   if part.split(" ", 1)[0].casefold() in names]
        if sorted(ordered) != sorted(names.values()):
            raise ValueError("Archived column definitions are incomplete: " + name)
        return tuple(ordered)
    return tuple(ddl_columns(sql, name, restricted=True))


def archived_columns(value, table):
    """Return this archive's own physical column order, never live DB columns."""
    saved = value.get("columns", {}).get(table)
    if saved is not None:
        if type(saved) is not list or any(type(column) is not str for column in saved):
            raise ValueError("Archived columns are invalid: " + table)
        return list(saved)
    definitions = [row[3] for row in value["schema"]
                   if len(row) == 4 and row[0] == "table" and row[1] == table]
    if len(definitions) != 1:
        raise ValueError("Archived table definition is missing or repeated: " + table)
    return list(_columns(definitions[0], table))


def _cell(value):
    # A SQLite cell can contain a BLOB/REAL marker; its stored JSON TEXT remains
    # a string. Do not reinterpret similar keys inside a business document.
    if type(value) is dict and set(value) == {"sqlite_blob_base64"}:
        value = base64.b64decode(value["sqlite_blob_base64"], validate=True)
    elif type(value) is dict and set(value) in ({"$sqlite_blob"}, {"$sqlite_real"}):
        value = unpacked(value)
    return packed(value)


def _rows(rows):
    result = []
    for row in rows:
        if type(row) is dict:
            result.append({name: _cell(value) for name, value in row.items()})
        elif isinstance(row, (list, tuple)):
            result.append([_cell(value) for value in row])
        else:
            raise ValueError("Archived SQLite row is invalid")
    return result


def _named_rows(value, table, rows):
    columns = archived_columns(value, table)
    result = []
    for row in rows:
        if type(row) is dict:
            result.append(dict(row))
        elif len(row) == len(columns):
            result.append(dict(zip(columns, row)))
        else:
            raise ValueError("Archived SQLite row does not match its columns: " + table)
    return result


def _comparison_rows(value, table, rows):
    # Legacy run archives already own physical positional values. New named
    # trial views use their captured columns to reach that same representation.
    if not any(type(row) is dict for row in rows):
        return _rows(rows)
    columns = archived_columns(value, table)
    ordered = []
    for row in rows:
        if type(row) is dict:
            if set(row) != set(columns):
                raise ValueError("Archived SQLite row does not match its columns: " + table)
            row = [row[name] for name in columns]
        ordered.append(row)
    return _rows(ordered)


def _version(value):
    rows = value["tables"].get("SchemaVersion", [])
    if len(rows) != 1:
        return None
    named = _named_rows(value, "SchemaVersion", rows)[0]
    return named.get("version") if type(named.get("version")) is int and named.get("id") == 1 else None


@lru_cache(maxsize=1)
def _read_model_schema():
    declared = {}
    for name, sql in read_model_objects().items():
        normalized = canonical_sql(sql)
        kind = normalized.split(" ", 2)[1].lower()
        table = name if kind == "table" else normalized.partition(" ON ")[2].split(" ", 1)[0].split("(", 1)[0]
        declared[name] = kind, table, normalized
    return declared


def _derived_schema(row):
    kind, name, table, sql = row
    expected = _read_model_schema().get(name)
    if expected is not None and (kind, table, canonical_sql(sql)) == expected:
        return True
    return (kind == "index" and table in READ_MODEL_TABLES
            and name == "sqlite_autoindex_" + table + "_1" and sql is None)


@lru_cache(maxsize=1)
def _business_role_schema():
    current, legacy = business_role_objects(), business_role_objects(legacy=True)
    return {name: (canonical_sql(sql), canonical_sql(legacy[name])) for name, sql in current.items()}


_PERFORMANCE_INDEXES = {name: canonical_sql(sql) for name, sql in {**ADDED, **REMOVED, **EFFICIENCY_INDEXES}.items()}


def _performance_index(row):
    kind, name, table, sql = row
    expected = _PERFORMANCE_INDEXES.get(name)
    return (kind == "index" and expected is not None and canonical_sql(sql or "") == expected
            and table == expected.partition(" ON ")[2].split("(", 1)[0])


def project_facts(value):
    """Pure comparison value; preserve other fields, old digests and unknown DDL."""
    current, legacy = _definitions(), _definitions(True)
    table_names = {row[1] for row in value["schema"] if len(row) == 4 and row[0] == "table"}
    tables = {name: _comparison_rows(value, name, rows) if name in table_names else rows
              for name, rows in value["tables"].items()}
    result = {key: item for key, item in value.items()
              if key != "columns" and not (key == "version" and item == "production-facts-v2")}
    result.update(schema=list(value["schema"]), tables=tables)
    if _version(value) not in (39, 40, 41, 42, 43, 44):
        return result
    for name in READ_MODEL_TABLES:
        tables.pop(name, None)
    schema, roles = [], _business_role_schema()
    for row in value["schema"]:
        if _derived_schema(row) or _performance_index(row):
            continue
        kind, name, table, sql = row
        if kind == "table" and table == name and name in roles and canonical_sql(sql) in roles[name]:
            schema.append((kind, name, table, roles[name][1]))
        elif kind == "table" and name in current and canonical_sql(sql) in (
                canonical_sql(current[name]), canonical_sql(legacy[name])):
            schema.append((kind, name, table, canonical_sql(legacy[name])))
            if name in tables:
                columns = list(_columns(current[name], name))
                rows = _named_rows(value, name, tables[name])
                tables[name] = [{**dict.fromkeys(columns), **item} for item in rows]
        else:
            schema.append(row)
    rows = _named_rows(value, "SchemaVersion", tables["SchemaVersion"])
    tables["SchemaVersion"] = [{**row, "version": 39, "updated_at": None} for row in rows]
    result["schema"] = schema
    return result

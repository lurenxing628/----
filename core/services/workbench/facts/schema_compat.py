"""Compare the declared v39/v40 representation without rewriting saved facts."""

import base64
from functools import lru_cache

from core.infrastructure.snapshot_connection import ddl_columns
from core.infrastructure.workbench_content_schema import CONTENT_TABLES, content_objects
from core.infrastructure.workbench_metadata_schema import canonical_ddl_parts, canonical_sql
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


def _version(value):
    rows = value["tables"].get("SchemaVersion", [])
    if len(rows) != 1:
        return None
    named = _named_rows(value, "SchemaVersion", rows)[0]
    return named.get("version") if type(named.get("version")) is int and named.get("id") == 1 else None


def project_facts(value):
    """Pure comparison value; preserve other fields, old digests and unknown DDL."""
    current, legacy = _definitions(), _definitions(True)
    table_names = {row[1] for row in value["schema"] if len(row) == 4 and row[0] == "table"}
    tables = {name: _rows(rows) if name in table_names else rows for name, rows in value["tables"].items()}
    result = {**value, "schema": list(value["schema"]), "tables": tables}
    if "columns" in value:
        result["columns"] = dict(value["columns"])
    if _version(value) not in (39, 40):
        return result
    schema = []
    for row in value["schema"]:
        kind, name, table, sql = row
        if kind == "table" and name in current and canonical_sql(sql) in (
                canonical_sql(current[name]), canonical_sql(legacy[name])):
            schema.append((kind, name, table, canonical_sql(legacy[name])))
            if name in tables:
                columns = list(_columns(current[name], name))
                rows = _named_rows(value, name, tables[name])
                tables[name] = [{**dict.fromkeys(columns), **item} for item in rows]
                if "columns" in result:
                    result["columns"][name] = columns
        else:
            schema.append(row)
    rows = _named_rows(value, "SchemaVersion", tables["SchemaVersion"])
    tables["SchemaVersion"] = [{**row, "version": 39, "updated_at": None} for row in rows]
    result["schema"] = schema
    return result

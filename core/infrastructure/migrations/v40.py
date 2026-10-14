"""Store original content while preserving every historical receipt and archive."""

import re

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.schema_structure import SchemaStructure
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_content_schema import CONTENT_TABLES, content_objects
from core.infrastructure.workbench_metadata_schema import canonical_sql

_ON_TABLE = re.compile(r'\bON\s+"?(\w+)"?', re.I)


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def _table(name, sql):
    if sql.lstrip().upper().startswith("CREATE TABLE"):
        return name
    match = _ON_TABLE.search(sql)
    return match.group(1) if match else None


def _validate(structure, current, legacy):
    for name, sql in current.items():
        if _table(name, sql) not in CONTENT_TABLES:
            continue
        actual = structure.sql.get(name)
        if actual is None or canonical_sql(actual) not in (canonical_sql(sql), canonical_sql(legacy[name])):
            raise RuntimeError("Content migration requires its declared historical structure: " + name)


def _rebuild(conn, structure, definitions):
    attached = [(name, item[2]) for name, item in structure.objects.items()
                if item[0] in ("index", "trigger") and item[1] in CONTENT_TABLES and item[2] is not None]
    sequences = {row[1]: (row[0], row[2]) for row in conn.execute("SELECT rowid,name,seq FROM sqlite_sequence")
                 if row[1] in CONTENT_TABLES}
    columns = {table: [row[1] for row in structure.table_info(table)] for table in CONTENT_TABLES}
    for table in CONTENT_TABLES:
        fields = ",".join(_quote(field) for field in columns[table])
        conn.execute("CREATE TEMP TABLE " + _quote("v40_" + table) + " AS SELECT rowid AS migration_rowid," +
                     fields + " FROM " + _quote(table))
    for table in reversed(CONTENT_TABLES):
        conn.execute("DROP TABLE " + _quote(table))
    for table in CONTENT_TABLES:
        conn.execute(definitions[table])
    for table in CONTENT_TABLES:
        fields = ",".join(_quote(field) for field in columns[table])
        conn.execute("INSERT INTO " + _quote(table) + " (rowid," + fields + ") SELECT migration_rowid," +
                     fields + " FROM " + _quote("v40_" + table) + " ORDER BY migration_rowid")
        conn.execute("DROP TABLE " + _quote("v40_" + table))
    for table in CONTENT_TABLES:
        conn.execute("DELETE FROM sqlite_sequence WHERE name=?", (table,))
    for name, (rowid, sequence) in sequences.items():
        conn.execute("INSERT INTO sqlite_sequence(rowid,name,seq) VALUES (?,?,?)", (rowid, name, sequence))
    # Restore original indexes and triggers after copying, so clocks and business
    # identity writers observe no technical inserts.
    for _name, sql in attached:
        conn.execute(sql)


def run(conn, logger=None):
    with TransactionManager(conn).transaction():
        structure = SchemaStructure(conn)
        definitions, legacy = content_objects(), content_objects(legacy=True)
        _validate(structure, definitions, legacy)
        if any(canonical_sql(structure.sql[table]) != canonical_sql(definitions[table]) for table in CONTENT_TABLES):
            _rebuild(conn, structure, definitions)
        if conn.execute("PRAGMA foreign_key_check").fetchone():
            raise RuntimeError("Content migration would break historical foreign keys.")
    return MigrationOutcome.APPLIED

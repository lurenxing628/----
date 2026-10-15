"""Extend native business roles without changing historical rows or plan identity."""

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.schedule_business_roles_schema import REBUILD_TABLES, contract_issues, objects
from core.infrastructure.schema_structure import SchemaStructure
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_metadata_schema import canonical_sql


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def _rebuild(conn, structure, definitions):
    attached = [(kind, name, sql) for name, (kind, table, sql) in structure.objects.items()
                if kind in ("index", "trigger") and table in REBUILD_TABLES and sql is not None]
    columns = {table: [row[1] for row in structure.table_info(table)] for table in REBUILD_TABLES}
    conn.execute("CREATE TEMP TABLE v42_candidate_sequence AS SELECT rowid AS migration_rowid,name,seq "
                 "FROM sqlite_sequence WHERE name IN (?,?,?)", REBUILD_TABLES)
    for table in REBUILD_TABLES:
        fields = ",".join(_quote(field) for field in columns[table])
        conn.execute("CREATE TEMP TABLE " + _quote("v42_" + table) + " AS SELECT rowid AS migration_rowid," +
                     fields + " FROM " + _quote(table))
    # Identity/clock writers stay detached for every technical delete and copy.
    for kind, name, _sql in attached:
        conn.execute("DROP " + kind.upper() + " " + _quote(name))
    for table in reversed(REBUILD_TABLES):
        conn.execute("DROP TABLE " + _quote(table))
    for table in REBUILD_TABLES:
        conn.execute(definitions[table])
    for table in REBUILD_TABLES:
        fields = ",".join(_quote(field) for field in columns[table])
        conn.execute("INSERT INTO " + _quote(table) + " (rowid," + fields + ") SELECT migration_rowid," +
                     fields + " FROM " + _quote("v42_" + table) + " ORDER BY migration_rowid")
        conn.execute("DROP TABLE " + _quote("v42_" + table))
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN (?,?,?)", REBUILD_TABLES)
    conn.execute("INSERT INTO sqlite_sequence(rowid,name,seq) SELECT migration_rowid,name,seq "
                 "FROM v42_candidate_sequence ORDER BY migration_rowid")
    conn.execute("DROP TABLE v42_candidate_sequence")
    for _kind, _name, sql in attached:
        conn.execute(sql)


def run(conn, logger=None):
    with TransactionManager(conn).transaction():
        structure, definitions = SchemaStructure(conn), objects()
        issues = contract_issues(conn, structure=structure, allow_legacy=True)
        if not structure.has_table("ScheduleCandidateRows"):
            issues.append("missing_table:ScheduleCandidateRows")
        if issues:
            raise RuntimeError("Business role migration requires its exact historical structure: " + "; ".join(issues))
        if any(canonical_sql(structure.sql[table]) != canonical_sql(sql) for table, sql in definitions.items()):
            definitions["ScheduleCandidateRows"] = structure.sql["ScheduleCandidateRows"]
            _rebuild(conn, structure, definitions)
        issues = contract_issues(conn)
        if issues:
            raise RuntimeError("Business role migration contract failed: " + "; ".join(issues))
        if conn.execute("PRAGMA foreign_key_check").fetchone():
            raise RuntimeError("Business role migration would break historical foreign keys.")
    return MigrationOutcome.APPLIED

"""Allow a new legacy-finish supplement after withdrawal, preserving all history."""

from core.infrastructure.material_stages_schema import contract_issues as material_contract_issues
from core.infrastructure.material_stages_schema import objects as material_objects
from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_execution_ledger_schema import (
    execution_ledger_contract_issues,
    execution_ledger_objects,
)
from core.infrastructure.workbench_execution_void_schema import execution_void_contract_issues, execution_void_objects
from core.infrastructure.workbench_metadata_schema import canonical_sql

_TABLES = ("WorkbenchProductionReports", "WorkbenchProductionReportRevisions", "WorkbenchProductionReportVoids")


def _replace_report_tables(conn):
    """Rebuild referencing children with their parent while foreign keys stay on."""
    definitions = {**execution_ledger_objects(), **execution_void_objects()}
    attached = conn.execute("""SELECT name,sql FROM sqlite_master WHERE tbl_name IN (?, ?, ?)
        AND sql IS NOT NULL""", _TABLES).fetchall()
    attached_names = {row[0] for row in attached}
    unknown = sorted(attached_names - definitions.keys())
    if unknown:
        raise RuntimeError("Unexpected execution report schema objects: " + ", ".join(unknown))
    for table in _TABLES:
        conn.execute(f"CREATE TEMP TABLE v37_{table} AS SELECT rowid AS migration_rowid,* FROM {table}")
    for table in reversed(_TABLES):
        conn.execute(f"DROP TABLE {table}")
    for table in _TABLES:
        conn.execute(definitions[table])
        fields = ",".join(row[1] for row in conn.execute(f"PRAGMA table_info({table})"))
        conn.execute(f"INSERT INTO {table} (rowid,{fields}) SELECT migration_rowid,{fields} FROM v37_{table} ORDER BY migration_rowid")
        conn.execute(f"DROP TABLE v37_{table}")
    # No reporting clock triggers run while original rows are copied.
    new_names = {"idx_wb_execution_reports_legacy", "wb_execution_legacy_link_active_unique"}
    for name, sql in definitions.items():
        if name not in _TABLES and (name in attached_names or name in new_names):
            conn.execute(sql)


def _migrate_report_links(conn):
    if not execution_ledger_contract_issues(conn) and not execution_void_contract_issues(conn):
        return
    issues = execution_ledger_contract_issues(conn, legacy_link_unique=True) + execution_void_contract_issues(conn)
    if issues:
        raise RuntimeError("Cannot migrate incomplete execution report history: " + "; ".join(issues))
    _replace_report_tables(conn)
    issues = execution_ledger_contract_issues(conn) + execution_void_contract_issues(conn)
    if issues:
        raise RuntimeError("Execution report migration contract failed: " + "; ".join(issues))


def _migrate_material_reviews(conn):
    if not material_contract_issues(conn):
        return
    definitions = material_objects()
    legacy = {name: sql for name, sql in definitions.items() if name != "wb_material_quantity_basis"}
    legacy["BatchMaterialReviews"] = legacy["BatchMaterialReviews"].replace(
        "batch_quantity INTEGER CHECK", "batch_quantity INTEGER NOT NULL CHECK")
    actual = dict(conn.execute("SELECT name,sql FROM sqlite_master"))
    if "wb_material_quantity_basis" in actual or any(
            name not in actual or canonical_sql(sql) != canonical_sql(actual[name] or "") for name, sql in legacy.items()):
        raise RuntimeError("Cannot migrate incomplete material review history.")
    # Accepted historical DDL can have a different physical column order.
    conn.execute("CREATE TEMP TABLE v37_BatchMaterialReviews AS "
                 "SELECT requirement_id,batch_quantity FROM BatchMaterialReviews")
    conn.execute("DROP TABLE BatchMaterialReviews")
    conn.execute(definitions["BatchMaterialReviews"])
    conn.execute("INSERT INTO BatchMaterialReviews(requirement_id,batch_quantity) "
                 "SELECT requirement_id,batch_quantity FROM v37_BatchMaterialReviews")
    conn.execute("DROP TABLE v37_BatchMaterialReviews")
    conn.execute(definitions["wb_material_quantity_basis"])


def run(conn, logger=None) -> MigrationOutcome:
    with TransactionManager(conn).transaction():
        _migrate_report_links(conn)
        _migrate_material_reviews(conn)
        if conn.execute("PRAGMA foreign_key_check").fetchone():
            raise RuntimeError("Execution/material migration would break historical foreign keys.")
    return MigrationOutcome.APPLIED

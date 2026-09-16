"""Append-only current-source confirmations; never rewrite operation birth evidence."""

from core.infrastructure.workbench_metadata_schema import _canonical_sql
from core.infrastructure.workbench_outsourcing_schema import contract_issues as outsourcing_issues


def workbench_outsourcing_source_objects():
    table = "WorkbenchOutsourcingSourceConfirmations"
    objects = {
        table: """CREATE TABLE WorkbenchOutsourcingSourceConfirmations (
            operation_ref TEXT PRIMARY KEY NOT NULL, batch_ref TEXT NOT NULL, fact_ref TEXT NOT NULL,
            FOREIGN KEY(operation_ref) REFERENCES WorkbenchOutsourcingOperationOrigins(operation_ref),
            FOREIGN KEY(batch_ref) REFERENCES WorkbenchEntityRefs(ref),
            FOREIGN KEY(fact_ref) REFERENCES WorkbenchOutsourcingFacts(fact_ref))""",
        "wb_outsourcing_source_confirmation_guard": """CREATE TRIGGER wb_outsourcing_source_confirmation_guard
            BEFORE INSERT ON WorkbenchOutsourcingSourceConfirmations BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM WorkbenchOutsourcingOperationOrigins o
                JOIN WorkbenchOutsourcingMembers m ON m.operation_ref=o.operation_ref
                JOIN WorkbenchOutsourcingReceipts r ON r.outsourcing_ref=m.outsourcing_ref
                JOIN WorkbenchOutsourcingFacts f ON f.outsourcing_ref=r.outsourcing_ref
                WHERE o.operation_ref=NEW.operation_ref AND o.batch_ref IS NULL
                AND r.batch_ref=NEW.batch_ref AND f.fact_ref=NEW.fact_ref AND f.sequence=1)
                THEN RAISE(ABORT,'outsourcing source confirmation must reference its first registration') END; END""",
    }
    for event in ("UPDATE", "DELETE"):
        name = "wb_outsourcing_source_confirmation_no_" + event.lower()
        objects[name] = ("CREATE TRIGGER " + name + " BEFORE " + event + " ON " + table +
                         " BEGIN SELECT RAISE(ABORT,'outsourcing source confirmation is permanent'); END")
    objects["wb_outsourcing_source_confirmation_no_replace"] = (
        "CREATE TRIGGER wb_outsourcing_source_confirmation_no_replace BEFORE INSERT ON " + table +
        " WHEN EXISTS(SELECT 1 FROM " + table + " WHERE operation_ref=NEW.operation_ref)"
        " BEGIN SELECT RAISE(ABORT,'outsourcing source confirmation cannot be replaced'); END")
    return objects


def workbench_outsourcing_source_contract_issues(conn):
    actual = {row[0]: row[1] for row in conn.execute("SELECT name,sql FROM sqlite_master")}
    return [("missing_outsourcing_source_schema:" if name not in actual else "invalid_outsourcing_source_schema:") + name
            for name, sql in workbench_outsourcing_source_objects().items()
            if name not in actual or _canonical_sql(sql) != _canonical_sql(actual[name] or "")]


def install_workbench_outsourcing_source_schema(conn):
    if not conn.in_transaction:
        raise RuntimeError("Outsourcing source installation requires the caller's migration transaction")
    definitions = workbench_outsourcing_source_objects()
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    issues = outsourcing_issues(conn)
    if names & set(definitions):
        issues += workbench_outsourcing_source_contract_issues(conn)
    if issues:
        raise RuntimeError("Cannot install or repair outsourcing source schema: " + ";".join(issues))
    if not names & set(definitions):
        for sql in definitions.values():
            conn.execute(sql)


objects = workbench_outsourcing_source_objects
contract_issues = workbench_outsourcing_source_contract_issues
install = install_workbench_outsourcing_source_schema

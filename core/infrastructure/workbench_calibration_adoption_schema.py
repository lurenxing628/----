"""Append-only calibration adoption history; current template hours remain revisable."""

from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_migration_contract_issues
from core.infrastructure.workbench_metadata_schema import _canonical_sql, workbench_metadata_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.infrastructure.workbench_template_lineage_schema import contract_issues as lineage_contract_issues

from .schema_structure import schema_objects

ADOPTIONS = "WorkbenchCalibrationAdoptions"
_REF = "TEXT NOT NULL CHECK(length({0})=48 AND {0} NOT GLOB '*[^0-9a-f]*')"


def _immutable_triggers(table, stem, keys):
    result = {}
    for event in ("update", "delete"):
        name = stem + "_no_" + event
        result[name] = ("CREATE TRIGGER " + name + " BEFORE " + event.upper() + " ON " + table +
                        " BEGIN SELECT RAISE(ABORT,'calibration adoption is immutable'); END")
    name = stem + "_no_replace"
    result[name] = ("CREATE TRIGGER " + name + " BEFORE INSERT ON " + table + " WHEN EXISTS (SELECT 1 FROM " + table +
                    " WHERE " + " OR ".join(key + "=NEW." + key for key in keys) +
                    ") BEGIN SELECT RAISE(ABORT,'calibration adoption cannot be replaced'); END")
    return result


def objects():
    result = {
        ADOPTIONS: """CREATE TABLE WorkbenchCalibrationAdoptions (
            adoption_ref """ + _REF.format("adoption_ref") + """ PRIMARY KEY,
            template_operation_ref TEXT NOT NULL REFERENCES WorkbenchEntityRefs(ref),
            request_key TEXT NOT NULL UNIQUE,
            template_revision_before INTEGER NOT NULL CHECK(typeof(template_revision_before)='integer' AND template_revision_before>0),
            template_revision_after INTEGER NOT NULL CHECK(typeof(template_revision_after)='integer' AND template_revision_after>=template_revision_before),
            old_unit_hours,
            new_unit_hours REAL NOT NULL CHECK(new_unit_hours>=0 AND new_unit_hours<=1.7976931348623157e308),
            reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 2000),
            declared_operator TEXT NOT NULL CHECK(length(trim(declared_operator)) BETWEEN 1 AND 100),
            confirmed INTEGER NOT NULL CHECK(typeof(confirmed)='integer' AND confirmed=1),
            application_operator TEXT NOT NULL CHECK(length(trim(application_operator)) BETWEEN 1 AND 512),
            adopted_at TEXT NOT NULL, generated_at TEXT NOT NULL,
            method_version TEXT NOT NULL,
            sample_count INTEGER NOT NULL CHECK(typeof(sample_count)='integer' AND sample_count BETWEEN 5 AND 20),
            evidence_json TEXT NOT NULL, template_before TEXT NOT NULL, template_after TEXT NOT NULL,
            FOREIGN KEY(request_key) REFERENCES WorkbenchCommandReceipts(request_key) DEFERRABLE INITIALLY DEFERRED
        )""",
    }
    result.update(_immutable_triggers(ADOPTIONS, "wb_calibration_adoption", ("adoption_ref", "request_key")))
    return result


def contract_issues(conn, *, structure=None):
    actual = schema_objects(conn, structure=structure)
    return [("missing_calibration_adoption:" if name not in actual else "invalid_calibration_adoption:") + name
            for name, sql in objects().items()
            if name not in actual or _canonical_sql(actual[name] or "") != _canonical_sql(sql)]


def install(conn):
    """Caller migration owns commit/rollback. Partial or changed DDL is rejected."""
    if not conn.in_transaction:
        raise RuntimeError("Calibration adoption installation requires the caller migration transaction.")
    declared = objects()
    actual = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    issues = (workbench_metadata_contract_issues(conn) + workbench_process_contract_issues(conn) +
              execution_ledger_migration_contract_issues(conn) + lineage_contract_issues(conn))
    if actual & set(declared):
        issues += contract_issues(conn)
    if issues:
        raise RuntimeError("Cannot install calibration adoption: " + "; ".join(issues))
    if not actual & set(declared):
        for sql in declared.values():
            conn.execute(sql)

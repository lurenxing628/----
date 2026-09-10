"""Unregistered next-version DDL; no business backfill or runtime installation."""

from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_contract_issues
from core.infrastructure.workbench_metadata_schema import _canonical_sql, workbench_metadata_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.infrastructure.workbench_template_lineage_schema import contract_issues as lineage_contract_issues

ADOPTIONS = "WorkbenchCalibrationAdoptions"
LOCKS = "WorkbenchCalibrationQuotaLocks"
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
            template_operation_ref TEXT NOT NULL UNIQUE REFERENCES WorkbenchEntityRefs(ref),
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
        LOCKS: """CREATE TABLE WorkbenchCalibrationQuotaLocks (
            template_operation_ref TEXT NOT NULL PRIMARY KEY REFERENCES WorkbenchEntityRefs(ref),
            adoption_ref TEXT NOT NULL UNIQUE REFERENCES WorkbenchCalibrationAdoptions(adoption_ref),
            locked_unit_hours REAL NOT NULL CHECK(locked_unit_hours>=0 AND locked_unit_hours<=1.7976931348623157e308),
            locked_at TEXT NOT NULL
        )""",
        "wb_calibration_quota_lock_origin": """CREATE TRIGGER wb_calibration_quota_lock_origin
            BEFORE INSERT ON WorkbenchCalibrationQuotaLocks BEGIN
            SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM WorkbenchCalibrationAdoptions a
                WHERE a.adoption_ref=NEW.adoption_ref AND a.template_operation_ref=NEW.template_operation_ref
                AND a.new_unit_hours IS NEW.locked_unit_hours AND a.adopted_at=NEW.locked_at)
                THEN RAISE(ABORT,'quota lock requires matching adoption audit') END;
        END""",
    }
    result.update(_immutable_triggers(ADOPTIONS, "wb_calibration_adoption", ("adoption_ref", "template_operation_ref", "request_key")))
    result.update(_immutable_triggers(LOCKS, "wb_calibration_quota_lock", ("template_operation_ref", "adoption_ref")))
    return result


def contract_issues(conn):
    actual = {row[0]: row[1] for row in conn.execute("SELECT name,sql FROM sqlite_master")}
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
              execution_ledger_contract_issues(conn) + lineage_contract_issues(conn))
    if actual & set(declared):
        issues += contract_issues(conn)
    if issues:
        raise RuntimeError("Cannot install calibration adoption: " + "; ".join(issues))
    if not actual & set(declared):
        for sql in declared.values():
            conn.execute(sql)

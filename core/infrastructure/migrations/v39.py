"""Retire permanent quota locks while preserving every adoption and receipt."""

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_calibration_adoption_legacy_schema import (
    ADOPTIONS,
    LOCKS,
)
from core.infrastructure.workbench_calibration_adoption_legacy_schema import (
    contract_issues as legacy_contract_issues,
)
from core.infrastructure.workbench_calibration_adoption_legacy_schema import (
    objects as legacy_objects,
)
from core.infrastructure.workbench_calibration_adoption_schema import objects


def run(conn, logger=None):
    with TransactionManager(conn).transaction():
        issues = legacy_contract_issues(conn)
        if issues:
            raise RuntimeError("Cannot retire quota locks: " + "; ".join(issues))
        for name in legacy_objects():
            if name not in (ADOPTIONS, LOCKS):
                conn.execute('DROP TRIGGER "' + name + '"')
        conn.execute("DROP TABLE WorkbenchCalibrationQuotaLocks")
        conn.execute("ALTER TABLE WorkbenchCalibrationAdoptions RENAME TO WorkbenchCalibrationAdoptions_v38")
        definitions = objects()
        conn.execute(definitions[ADOPTIONS])
        columns = (
            "adoption_ref,template_operation_ref,request_key,template_revision_before,"
            "template_revision_after,old_unit_hours,new_unit_hours,reason,declared_operator,"
            "confirmed,application_operator,adopted_at,generated_at,method_version,"
            "sample_count,evidence_json,template_before,template_after"
        )
        conn.execute(
            f"INSERT INTO WorkbenchCalibrationAdoptions({columns}) "
            f"SELECT {columns} FROM WorkbenchCalibrationAdoptions_v38"
        )
        conn.execute("DROP TABLE WorkbenchCalibrationAdoptions_v38")
        for name, sql in definitions.items():
            if name != ADOPTIONS:
                conn.execute(sql)
    return MigrationOutcome.APPLIED

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
        conn.execute("INSERT INTO WorkbenchCalibrationAdoptions SELECT * FROM WorkbenchCalibrationAdoptions_v38")
        conn.execute("DROP TABLE WorkbenchCalibrationAdoptions_v38")
        for name, sql in definitions.items():
            if name != ADOPTIONS:
                conn.execute(sql)
    return MigrationOutcome.APPLIED

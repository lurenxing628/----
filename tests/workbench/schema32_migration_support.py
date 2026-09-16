"""Frozen v31 evidence, independent from current schema/version constants."""

import hashlib
from pathlib import Path

from core.infrastructure.migration_state import set_schema_version
from core.infrastructure.migrations import v31
from core.infrastructure.workbench_execution_void_schema import execution_void_objects
from core.infrastructure.workbench_outsourcing_source_schema import objects as source_objects
from tests.workbench.calibration_dashboard_migration_support import canonical_object
from tests.workbench.dashboard_external_migration_support import seed_v30
from tests.workbench.legacy_migration_current_support import V32_TABLES as V32_TABLES
from tests.workbench.legacy_migration_current_support import assert_v32_empty as assert_v32_empty
from tests.workbench.legacy_migration_current_support import missing_v32_issues as missing_v32_issues
from tests.workbench.run_schema_migration_support import connect, source_ddl

FIXTURE_V31 = Path(__file__).parent / "fixtures" / "schema-v31.sql"
FIXTURE_V31_SHA = "b939a2d6516925863e6f7f0fb3db32ea83a94e4204a8df8c1f6574953bb17b47"


def objects():
    return dict(source_objects(), **execution_void_objects())


def frozen_v31(path):
    ddl = FIXTURE_V31.read_bytes()
    assert hashlib.sha256(ddl).hexdigest() == FIXTURE_V31_SHA
    conn = connect(path)
    conn.executescript(ddl.decode("utf-8"))
    set_schema_version(conn, 31)
    conn.commit()
    return conn


def seed_v31(path):
    conn = seed_v30(path)
    v31.run(conn)
    set_schema_version(conn, 31)
    conn.commit()
    with frozen_v31(":memory:") as expected:
        assert list(map(canonical_object, source_ddl(conn))) == list(map(canonical_object, source_ddl(expected)))
    return conn

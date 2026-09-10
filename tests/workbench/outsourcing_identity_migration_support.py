"""Frozen v29 business evidence, not a relabeled current-schema database."""

import hashlib
from pathlib import Path

from core.infrastructure.migration_state import set_schema_version
from core.infrastructure.migrations import v29
from core.infrastructure.transaction import TransactionManager
from tests.workbench.calibration_dashboard_migration_support import canonical_object, seed_v28
from tests.workbench.run_schema_migration_support import connect, source_ddl

FIXTURE_V29 = Path(__file__).parent / "fixtures" / "schema-v29.sql"
FIXTURE_V29_SHA = "d303a3b004546845c214d3907e1dc27c8c630132da2096feaaa15ed374333648"


def seed_v29(path):
    conn = seed_v28(path)
    with TransactionManager(conn).transaction():
        v29.run(conn)
        set_schema_version(conn, 29)
    assert hashlib.sha256(FIXTURE_V29.read_bytes()).hexdigest() == FIXTURE_V29_SHA
    with connect(":memory:") as expected:
        expected.executescript(FIXTURE_V29.read_text(encoding="utf-8"))
        assert list(map(canonical_object, source_ddl(conn))) == list(map(canonical_object, source_ddl(expected)))
    return conn


def expected_origins(conn):
    return set(map(tuple, conn.execute("""SELECT r.ref,(SELECT e.batch_ref
        FROM WorkbenchTemplateLineageEvents e WHERE e.operation_ref=r.ref AND e.event_type='created'
        ORDER BY e.event_id LIMIT 1) FROM WorkbenchPlanSourceRefs r JOIN BatchOperations o
        ON r.source_key=CAST(o.id AS TEXT) WHERE r.kind='operation' AND r.active=1""")))

"""Frozen v29 business evidence, not a relabeled current-schema database."""

from pathlib import Path

from tests.workbench.frozen_business_seed_support import seed_frozen_business

FIXTURE_V29 = Path(__file__).parent / "fixtures" / "schema-v29.sql"
FIXTURE_V29_SHA = "d303a3b004546845c214d3907e1dc27c8c630132da2096feaaa15ed374333648"


def seed_v29(path):
    return seed_frozen_business(path, 29)


def expected_origins(conn):
    return set(map(tuple, conn.execute("""SELECT r.ref,(SELECT e.batch_ref
        FROM WorkbenchTemplateLineageEvents e WHERE e.operation_ref=r.ref AND e.event_type='created'
        ORDER BY e.event_id LIMIT 1) FROM WorkbenchPlanSourceRefs r JOIN BatchOperations o
        ON r.source_key=CAST(o.id AS TEXT) WHERE r.kind='operation' AND r.active=1""")))

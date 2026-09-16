"""Historical v28 with real completed candidates, execution, lineage and a scenario."""

from pathlib import Path

from core.infrastructure.workbench_metadata_schema import _canonical_sql
from tests.workbench.frozen_business_seed_support import seed_frozen_business

FIXTURE_V28 = Path(__file__).parent / "fixtures" / "schema-v28.sql"
FIXTURE_V28_SHA = "2520295cebbe708270f93ed0aa5a6b18ea9b93ad3a1c77dd6c7a857fea44ad52"


def canonical_object(row):
    return row[:3], _canonical_sql(row[3] or "")


def seed_v28(path):
    return seed_frozen_business(path, 28)

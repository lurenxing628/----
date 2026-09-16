"""Fixed v26 storage with old execution facts and genuine persisted candidates."""

from pathlib import Path

from tests.workbench.frozen_business_seed_support import seed_frozen_business

FIXTURE_V26 = Path(__file__).parent / "fixtures" / "schema-v26.sql"


def seed_v26(path):
    return seed_frozen_business(path, 26)

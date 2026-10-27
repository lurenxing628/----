"""v41 backfill cannot derive read models from run archives written before the current form."""

import pytest

from core.infrastructure.migration_state import get_schema_version, set_schema_version
from core.infrastructure.migrations import run_migration
from core.infrastructure.workbench_run_read_model_schema import READ_MODEL_TABLES
from tests.workbench.frozen_business_seed_support import seed_frozen_business
from tests.workbench.run_schema_migration_support import snapshot


def test_v40_archive_backfill_of_old_runs_fails_and_rolls_back(tmp_path):
    conn = seed_frozen_business(tmp_path / "historical-v40.sqlite", 30)
    try:
        with conn:
            for version in range(31, 41):
                run_migration(conn, version)
                set_schema_version(conn, version)
        assert get_schema_version(conn) == 40
        before = snapshot(conn)
        assert not set(READ_MODEL_TABLES) & before.keys()
        # 冻结样例里的旧运行存档不是现行写入形态，v41 回填不了：迁移报错并整体回滚，库停在 v40。
        # 迁移链不再为旧存档维护兼容（报错类型随 v41 现状而定，不在这里锁定）。
        with pytest.raises(Exception):
            with conn:
                run_migration(conn, 41)
                set_schema_version(conn, 41)
        assert get_schema_version(conn) == 40
        assert snapshot(conn) == before
    finally:
        conn.close()

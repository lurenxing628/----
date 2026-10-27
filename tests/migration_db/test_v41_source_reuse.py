"""v41 backfill cannot read run archives written before the current candidate archive form."""

from collections import OrderedDict

import pytest

from core.infrastructure.migrations.v41 import _candidate_provider
from core.services.workbench.facts.candidate_store import CandidateStore
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests.workbench.frozen_business_seed_support import seed_frozen_business


def test_v41_cannot_read_frozen_run_archive():
    conn = seed_frozen_business(":memory:", 30)
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        repo, source_cache = WorkbenchRunRepository(conn), OrderedDict()
        candidate_ref = conn.execute(
            "SELECT candidate_ref FROM WorkbenchRunCandidates ORDER BY sequence LIMIT 1").fetchone()[0]
        current = {"run": {"run_ref": "f" * 48}, "rows": []}
        # 冻结样例里的旧运行存档不是现行写入形态，读不出来源，也不进缓存（报错类型随 v41 现状而定，不在这里锁定）。
        with pytest.raises(Exception):
            _candidate_provider(CandidateStore(conn), repo, current, source_cache=source_cache)(candidate_ref)
        assert not source_cache
    finally:
        conn.close()

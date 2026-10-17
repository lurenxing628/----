"""Reuse immutable sources across migration owners without retaining all history."""

from collections import Counter, OrderedDict

from core.infrastructure.migrations.v41 import _candidate_provider
from core.services.workbench.facts.candidate_store import CandidateStore
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests.workbench.frozen_business_seed_support import seed_frozen_business


def _observed_store(conn, monkeypatch):
    store, reads = CandidateStore(conn), Counter()
    for name in ("capture", "tasks"):
        original = getattr(store, name)

        def observed(key, original=original, name=name):
            reads[name, key] += 1
            return original(key)

        monkeypatch.setattr(store, name, observed)
    return store, reads


def test_v41_reuses_one_verified_source_across_independent_run_owners(monkeypatch):
    conn = seed_frozen_business(":memory:", 30)
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        store, reads = _observed_store(conn, monkeypatch)
        repo, source_cache = WorkbenchRunRepository(conn), OrderedDict()
        candidate_ref, run_ref = conn.execute(
            "SELECT candidate_ref,run_ref FROM WorkbenchRunCandidates ORDER BY sequence LIMIT 1").fetchone()
        current = {"run": {"run_ref": "f" * 48}, "rows": []}
        first = None
        for _ in range(12):
            source = _candidate_provider(store, repo, current, source_cache=source_cache)(candidate_ref)
            if first is None:
                first = source
            assert source is first
        assert source.candidate["candidate_ref"] == candidate_ref
        assert len(source.raw_tasks) == source.candidate["task_count"] == 1
        assert reads == Counter({("capture", run_ref): 1, ("tasks", candidate_ref): 1})
    finally:
        conn.close()


def test_v41_source_cache_evicts_the_least_recent_identity(monkeypatch):
    conn = seed_frozen_business(":memory:", 30)
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        store, reads = _observed_store(conn, monkeypatch)
        repo, source_cache = WorkbenchRunRepository(conn), OrderedDict()
        refs = [row[0] for row in conn.execute(
            "SELECT candidate_ref FROM WorkbenchRunCandidates ORDER BY sequence LIMIT 3")]
        current = {"run": {"run_ref": "f" * 48}, "rows": []}
        for ref in (refs[0], refs[1], refs[0], refs[2]):
            _candidate_provider(store, repo, current, source_cache=source_cache)(ref)
            assert len(source_cache) <= 2
        assert list(source_cache) == [refs[0], refs[2]]
        _candidate_provider(store, repo, current, source_cache=source_cache)(refs[1])
        assert list(source_cache) == [refs[2], refs[1]]
        assert {ref: reads["tasks", ref] for ref in refs} == {refs[0]: 1, refs[1]: 2, refs[2]: 1}
    finally:
        conn.close()

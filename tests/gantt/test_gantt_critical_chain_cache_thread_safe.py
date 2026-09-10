"""回归测试：GanttCriticalChainProvider.get_critical_chain 的 LRU 缓存在 10 线程并发访问下不出现底层 OrderedDict 重叠访问（用探针 dict 验证无并发命中），缓存条目数不超过 _CRITICAL_CHAIN_CACHE_MAX，且 cache_hit 契约成立（同 version 首次 miss、二次 hit），返回 dict 含 ids/available/reason/cache_hit 字段。"""

from __future__ import annotations

import contextlib
import random
import sqlite3
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List

from tests.gantt.gantt_critical_chain_cache_support import cache_db, reset_cache


class ConcurrencyProbeOrderedDict(OrderedDict):
    def __init__(self):
        super().__init__()
        self._active = 0
        self._guard = threading.Lock()
        self.concurrent_hits = 0

    @contextlib.contextmanager
    def _probe(self):
        with self._guard:
            self._active += 1
            if self._active > 1:
                self.concurrent_hits += 1
        try:
            # 故意让出执行时间片，放大无锁实现的并发重叠窗口。
            # 使用 sleep(0) 避免 Windows 短 sleep 粒度导致测试过慢。
            time.sleep(0)
            yield
        finally:
            with self._guard:
                self._active -= 1

    def get(self, key, default=None):
        with self._probe():
            return super().get(key, default)

    def move_to_end(self, key, last=True):
        with self._probe():
            return super().move_to_end(key, last=last)

    def __setitem__(self, key, value):
        with self._probe():
            return super().__setitem__(key, value)

    def popitem(self, last=True):
        with self._probe():
            return super().popitem(last=last)

    def __len__(self):
        with self._probe():
            return super().__len__()


def test_gantt_critical_chain_cache_thread_safe(monkeypatch, tmp_path) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module
    from core.services.scheduler.gantt_critical_chain_provider import GanttCriticalChainProvider
    from data.repositories import ScheduleRepository

    reset_cache(monkeypatch, cache_max=8)
    probe_cache = ConcurrencyProbeOrderedDict()
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE", probe_cache)
    compute_count = {"value": 0}
    query_count = {"value": 0}
    counters_lock = threading.Lock()
    original_compute = provider_module.compute_critical_chain

    def _compute(schedule_repo, version: int) -> Dict[str, Any]:
        time.sleep(0.001)
        with counters_lock:
            compute_count["value"] += 1
        return original_compute(schedule_repo, version)

    def _trace_query(sql):
        if "LEFT JOIN BatchOperations" in sql:
            with counters_lock:
                query_count["value"] += 1

    monkeypatch.setattr(provider_module, "compute_critical_chain", _compute)
    path = tmp_path / "critical-chain-concurrent.db"
    with cache_db(path=path) as case:
        case.conn.executemany(
            "INSERT INTO Schedule(op_id, machine_id, start_time, end_time, version, created_at) "
            "SELECT op_id, machine_id, start_time, end_time, ?, created_at FROM Schedule WHERE version = 1",
            [(version,) for version in list(range(2, 33)) + [999]],
        )
        case.conn.commit()
        errors: List[Exception] = []
        ready = threading.Barrier(10)

        def _worker(seed: int) -> None:
            rng = random.Random(seed)
            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row
            conn.set_trace_callback(_trace_query)
            try:
                provider = GanttCriticalChainProvider(conn=conn, schedule_repo=ScheduleRepository(conn))
                ready.wait(timeout=5)
                for _ in range(80):
                    version = rng.randint(1, 32)
                    cc = provider.get_critical_chain(version)
                    if not isinstance(cc, dict):
                        raise RuntimeError("critical_chain 返回类型异常")
                    if "ids" not in cc or "available" not in cc or "reason" not in cc or "cache_hit" not in cc:
                        raise RuntimeError(f"critical_chain 缺少字段：{cc}")
                    assert cc["available"] is True
                    assert cc["ids"] == ["A", "B"]
                    assert cc["edges"][0]["edge_type"] == "machine"
            except Exception as exc:
                errors.append(exc)
            finally:
                conn.close()

        threads = [threading.Thread(target=_worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if errors:
            raise errors[0]
        assert probe_cache.concurrent_hits == 0
        assert len(probe_cache) <= GanttCriticalChainProvider._CRITICAL_CHAIN_CACHE_MAX
        assert query_count["value"] == 800
        assert 0 < compute_count["value"] <= query_count["value"]

        # 单线程阶段精确区分每请求明细读取、命中不重算和内容变更重算。
        provider = case.provider
        case.conn.set_trace_callback(_trace_query)
        queries_before = query_count["value"]
        computes_before = compute_count["value"]
        first = provider.get_critical_chain(999)
        assert first["cache_hit"] is False
        assert first["ids"] == ["A", "B"]
        first["ids"].append("caller-mutation")
        first["edges"][0]["from"] = "caller-mutation"
        second = provider.get_critical_chain(999)
        assert second["cache_hit"] is True
        assert second["ids"] == ["A", "B"]
        assert second["edges"][0]["from"] == "A"
        assert query_count["value"] == queries_before + 2
        assert compute_count["value"] == computes_before + 1

        aggregate_sql = "SELECT COUNT(*), MAX(id), MAX(created_at) FROM Schedule WHERE version = 999"
        old_aggregate = tuple(case.conn.execute(aggregate_sql).fetchone())
        case.conn.execute("UPDATE Schedule SET machine_id = 'M2' WHERE version = 999 AND op_id = 2")
        case.conn.commit()
        assert tuple(case.conn.execute(aggregate_sql).fetchone()) == old_aggregate
        changed = provider.get_critical_chain(999)
        assert changed["ids"] == ["B"]
        assert changed["cache_hit"] is False
        assert query_count["value"] == queries_before + 3
        assert compute_count["value"] == computes_before + 2
        stable = provider.get_critical_chain(999)
        assert stable["ids"] == ["B"]
        assert stable["cache_hit"] is True
        assert query_count["value"] == queries_before + 4
        assert compute_count["value"] == computes_before + 2
        assert probe_cache.concurrent_hits == 0
        assert len(probe_cache) <= GanttCriticalChainProvider._CRITICAL_CHAIN_CACHE_MAX

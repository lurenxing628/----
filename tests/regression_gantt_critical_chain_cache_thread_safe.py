from __future__ import annotations

import contextlib
import os
import random
import sys
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


class _DummyCursor:
    def __init__(self, db_file: str):
        self._db_file = str(db_file)

    def fetchall(self):
        return [(0, "main", self._db_file)]


class _DummyConn:
    def __init__(self, db_file: str):
        self._db_file = str(db_file)

    def execute(self, sql: str):
        if "pragma database_list" not in str(sql or "").strip().lower():
            raise RuntimeError(f"unexpected sql in test: {sql!r}")
        return _DummyCursor(self._db_file)


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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import core.services.scheduler.gantt_service as gantt_module
    from core.services.scheduler.gantt_service import GanttService

    probe_cache = ConcurrencyProbeOrderedDict()
    compute_count = {"value": 0}
    compute_count_lock = threading.Lock()

    def _fake_compute(_schedule_repo, version: int) -> Dict[str, Any]:
        time.sleep(0.001)
        with compute_count_lock:
            compute_count["value"] += 1
        return {
            "ids": [f"B{int(version)}"],
            "edges": [],
            "makespan_end": None,
            "edge_type_stats": {"process": 0, "machine": 0, "operator": 0, "unknown": 0},
            "edge_count": 0,
            "available": True,
            "reason": "",
        }

    old_cache = GanttService._CRITICAL_CHAIN_CACHE
    old_lock = GanttService._CRITICAL_CHAIN_CACHE_LOCK
    old_max = GanttService._CRITICAL_CHAIN_CACHE_MAX
    old_compute = gantt_module.compute_critical_chain

    conn = _DummyConn(db_file=os.path.join(repo_root, "db", "aps.db"))
    svc = GanttService(conn)
    errors: List[Exception] = []

    try:
        GanttService._CRITICAL_CHAIN_CACHE = probe_cache
        GanttService._CRITICAL_CHAIN_CACHE_LOCK = threading.Lock()
        GanttService._CRITICAL_CHAIN_CACHE_MAX = 8
        gantt_module.compute_critical_chain = _fake_compute

        def _worker(seed: int) -> None:
            rng = random.Random(seed)
            try:
                for _ in range(80):
                    version = rng.randint(1, 32)
                    cc = svc._get_critical_chain(version)
                    if not isinstance(cc, dict):
                        raise RuntimeError("critical_chain 返回类型异常")
                    if "ids" not in cc or "available" not in cc or "reason" not in cc or "cache_hit" not in cc:
                        raise RuntimeError(f"critical_chain 缺少字段：{cc}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if errors:
            raise errors[0]
        if probe_cache.concurrent_hits > 0:
            raise RuntimeError(f"检测到缓存并发访问重叠：{probe_cache.concurrent_hits}")

        # 容量契约：LRU 缓存条目数不应超过上限。
        if len(GanttService._CRITICAL_CHAIN_CACHE) > int(GanttService._CRITICAL_CHAIN_CACHE_MAX):
            raise RuntimeError("critical_chain 缓存容量超过上限")

        # cache_hit 契约：同 key 连续调用，第二次应命中缓存。
        first = svc._get_critical_chain(999)
        second = svc._get_critical_chain(999)
        if bool(first.get("cache_hit")):
            raise RuntimeError(f"首次调用不应命中缓存：{first}")
        if not bool(second.get("cache_hit")):
            raise RuntimeError(f"二次调用应命中缓存：{second}")
        if int(compute_count["value"]) <= 0:
            raise RuntimeError("测试桩 compute 未被调用")

        print("OK")
    finally:
        GanttService._CRITICAL_CHAIN_CACHE = old_cache
        GanttService._CRITICAL_CHAIN_CACHE_LOCK = old_lock
        GanttService._CRITICAL_CHAIN_CACHE_MAX = old_max
        gantt_module.compute_critical_chain = old_compute


if __name__ == "__main__":
    main()

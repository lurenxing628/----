"""Observe actual worker stages without replacing results or suppressing failures."""

import cProfile
import json
import sys
import threading
import time
from contextlib import ExitStack, contextmanager
from functools import wraps
from unittest.mock import patch


def peak_rss_bytes():
    if sys.platform not in ("darwin", "linux"):
        return None
    import resource

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


@contextmanager
def observe_worker(directory, *, profile=False):
    from core.services.workbench import run_worker

    origin = time.monotonic()
    path, lock = directory / "worker-stages.jsonl", threading.Lock()

    def wrap(name, function):
        @wraps(function)
        def call(*args, **kwargs):
            started, completed = time.monotonic(), False
            profiler = cProfile.Profile() if profile and name == "engine" else None
            if profiler is not None:
                profiler.enable()
            try:
                value = function(*args, **kwargs)
                completed = True
                return value
            finally:
                ended = time.monotonic()
                if profiler is not None:
                    profiler.disable()
                    profiler.dump_stats(str(directory / "managed-engine.pstats"))
                item = {"stage": name, "started_seconds": started - origin, "ended_seconds": ended - origin,
                        "elapsed_seconds": ended - started, "completed": completed,
                        "thread_id": threading.get_ident(), "cprofile_enabled": profiler is not None,
                        "peak_rss_bytes": peak_rss_bytes()}
                with lock, path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(item) + "\n")
        return call

    with ExitStack() as stack:
        for name, attribute in (("prepare", "prepare_candidate_run_input"), ("engine", "compute_prepared_candidate_run"),
                                ("serialization", "prepare_run_result")):
            stack.enter_context(patch.object(run_worker, attribute, wrap(name, getattr(run_worker, attribute))))
        for name, attribute in (("snapshot_compute_serialize", "_compute"), ("persistence", "_persist"), ("worker_total", "execute")):
            stack.enter_context(patch.object(run_worker.WorkbenchRunWorker, attribute,
                                            wrap(name, getattr(run_worker.WorkbenchRunWorker, attribute))))
        yield

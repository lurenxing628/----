"""Load the application after recording the lightweight Python startup boundary."""

import os
import time

from .launcher_observability import launcher_log_warning
from .launcher_paths import resolve_prelaunch_log_dir
from .paths import runtime_base_dir


def load_entrypoint(anchor_file, python_started_at):
    runtime_dir = runtime_base_dir(anchor_file=anchor_file)
    log_dir = resolve_prelaunch_log_dir(runtime_dir)
    launcher_log_warning(None, "启动阶段 python_entry pid=%s elapsed=%.3fs，开始加载应用模块。",
                         os.getpid(), time.perf_counter() - python_started_at,
                         state_dir=log_dir, logger_level="info")
    started = time.perf_counter()
    from web.bootstrap import entrypoint

    launcher_log_warning(None, "启动阶段 application_import_complete pid=%s duration=%.3fs。",
                         os.getpid(), time.perf_counter() - started,
                         state_dir=log_dir, logger_level="info")
    return entrypoint

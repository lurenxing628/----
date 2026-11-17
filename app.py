from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

_PYTHON_STARTED_AT = time.perf_counter()

if TYPE_CHECKING:
    from flask import Flask

PRELAUNCH_PUBLIC_MESSAGE = "应用启动失败：程序文件加载失败，请把 launcher.log 发给维护人员排查。"


def _record_prelaunch_import_failure(exc: BaseException) -> None:
    from web.bootstrap.launcher_observability import write_launch_error
    from web.bootstrap.launcher_paths import resolve_prelaunch_log_dir
    from web.bootstrap.paths import runtime_base_dir

    runtime_dir = runtime_base_dir(anchor_file=__file__)
    write_launch_error(
        None,
        "应用启动前加载失败：%s",
        exc,
        state_dir=resolve_prelaunch_log_dir(runtime_dir),
        runtime_dir=runtime_dir,
        public_message=PRELAUNCH_PUBLIC_MESSAGE,
    )


def _entrypoint_module() -> Any:
    from web.bootstrap.entrypoint_loader import load_entrypoint

    return load_entrypoint(__file__, _PYTHON_STARTED_AT)


def create_app() -> Flask:
    return _entrypoint_module().create_app()


def main(argv=None, deps=None) -> int:
    try:
        entrypoint = _entrypoint_module()
    except Exception as exc:
        _record_prelaunch_import_failure(exc)
        return 14
    return int(entrypoint.app_main(anchor_file=__file__, argv=argv, deps=deps))


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    raise SystemExit(main())

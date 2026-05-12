from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flask import Flask

PRELAUNCH_PUBLIC_MESSAGE = "应用启动失败：程序文件加载失败，请把 launcher.log 发给维护人员排查。"


def _record_prelaunch_import_failure(exc: BaseException) -> bool:
    from web.bootstrap.launcher_observability import launcher_log_warning
    from web.bootstrap.launcher_paths import resolve_prelaunch_log_dir
    from web.bootstrap.paths import runtime_base_dir

    runtime_dir = runtime_base_dir(anchor_file=__file__)
    log_dir = resolve_prelaunch_log_dir(runtime_dir)
    result = launcher_log_warning(
        None,
        "应用启动前加载失败：%s",
        exc,
        runtime_dir=runtime_dir,
        state_dir=log_dir,
        write_launch_error=True,
        logger_level="error",
        public_launch_error_message=PRELAUNCH_PUBLIC_MESSAGE,
    )
    if result.file_ok and not result.error_file_ok:
        launcher_log_warning(
            None,
            "写入启动错误提示文件失败。",
            runtime_dir=runtime_dir,
            state_dir=log_dir,
            write_launch_error=False,
            logger_level="error",
        )
    return bool(result.file_ok)


def _entrypoint_module() -> Any:
    from web.bootstrap import entrypoint

    return entrypoint


def create_app() -> Flask:
    return _entrypoint_module().create_app_with_mode("default")


if __name__ != "__main__":
    try:
        app = create_app()
    except Exception as exc:
        _record_prelaunch_import_failure(exc)
        raise RuntimeError(PRELAUNCH_PUBLIC_MESSAGE) from None


def main(argv=None, deps=None) -> int:
    try:
        entrypoint = _entrypoint_module()
    except Exception as exc:
        _record_prelaunch_import_failure(exc)
        return 14
    return int(entrypoint.app_main("default", anchor_file=__file__, argv=argv, deps=deps))


if __name__ == "__main__":
    raise SystemExit(main())

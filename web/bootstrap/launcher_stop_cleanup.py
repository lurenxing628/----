from __future__ import annotations

from typing import Callable

from .launcher_cleanup_result import RuntimeCleanupFailure, RuntimeCleanupResult
from .launcher_observability import launcher_log_warning


def delete_runtime_contract_files_result_for_stop(
    state_dir: str,
    *,
    delete_runtime_contract_files: Callable[[str], None],
    delete_runtime_contract_files_result: Callable[[str], RuntimeCleanupResult],
    default_delete_runtime_contract_files: Callable[[str], None],
    default_delete_runtime_contract_files_result: Callable[[str], RuntimeCleanupResult],
) -> RuntimeCleanupResult:
    if delete_runtime_contract_files is not default_delete_runtime_contract_files and (
        delete_runtime_contract_files_result is default_delete_runtime_contract_files_result
    ):
        try:
            delete_runtime_contract_files(state_dir)
        except Exception as exc:
            launcher_log_warning(
                None,
                "运行时旧清理入口失败，停止命令按清理失败处理：state_dir=%s error=%s",
                state_dir,
                exc,
                state_dir=state_dir,
                write_launch_error=True,
            )
            return RuntimeCleanupResult(
                state_dir=str(state_dir),
                target_dirs=(str(state_dir),),
                attempted_paths=(),
                removed_paths=(),
                missing_paths=(),
                failures=(RuntimeCleanupFailure(path=str(state_dir), reason="legacy_cleanup_failed", error=str(exc)),),
            )
        return RuntimeCleanupResult(
            state_dir=str(state_dir),
            target_dirs=(str(state_dir),),
            attempted_paths=(),
            removed_paths=(),
            missing_paths=(),
            failures=(),
        )
    return delete_runtime_contract_files_result(state_dir)

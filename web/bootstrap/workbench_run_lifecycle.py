"""Join managed computations before exit backups and release of launcher locks."""

from .workbench_request_lifecycle import lookup_workbench_request_lifecycle
from .workbench_system_restore_recovery import (
    RECOVERY,
    WorkbenchSystemRestoreRecoveryHost,
    configure_system_restore_recovery,
    prepare_system_restore_startup,
)


def stop_run_runtime(runtime):
    database_path = getattr(runtime, "db_path", None)
    if database_path is not None:
        gate = lookup_workbench_request_lifecycle(database_path)
        if gate is not None and gate.shutdown(wait=True) is not True:
            raise RuntimeError("仍有请求或数据库连接未安全结束，不能释放数据库运行锁。")
    if runtime is not None and runtime.shutdown(wait=True) is not True:
        raise RuntimeError("排产后台线程尚未停止，不能释放数据库运行锁。")


def install_run_lifecycle(deps, app, lock_state):
    from .workbench_system_restore import install_workbench_system_restore_host

    installer = deps.install_run_runtime
    if installer is None:
        return None
    if app.extensions.get(RECOVERY) or prepare_system_restore_startup(app):
        return _install_recovery_lifecycle(deps, app, lock_state)
    runtime = installer(app, runtime_lock=lock_state.get("payload"))
    lock_state["runtime"] = runtime
    # Registered after factory's exit backup, hence called before it by atexit.
    deps.atexit_register(stop_run_runtime, runtime)
    if not runtime.ready:
        raise RuntimeError("排产运行恢复检查未通过：" + str(runtime.status["reason"]))
    try:
        install_workbench_system_restore_host(app, runtime=runtime)
    except Exception:
        # A journal/ownership check can fail after the worker was installed.
        # Never publish that half-assembled runtime as an accepting instance.
        app.logger.exception("Restore host installation failed; closing normal runtime")
        stop_run_runtime(runtime)
        configure_system_restore_recovery(app)
        return _install_recovery_lifecycle(deps, app, lock_state)
    return runtime


def _install_recovery_lifecycle(deps, app, lock_state):
    host = WorkbenchSystemRestoreRecoveryHost(app, lock_state.get("payload"))
    lock_state["runtime"] = host
    deps.atexit_register(stop_run_runtime, host)
    return host


def release_runtime_after_jobs(deps, lock_state, lock_scope, pid, db_path):
    runtime = lock_state.get("runtime")
    stop_run_runtime(runtime)
    directory = lock_state.get("contract_cleanup_dir")
    if directory is not None:
        runtime.proof.verify()
        deps.delete_runtime_contract_files(directory)
    deps.release_runtime_lock(lock_scope, pid, db_path)

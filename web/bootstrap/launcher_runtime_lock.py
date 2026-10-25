"""运行时互斥锁生命周期（从 launcher_contracts 按职责拆出）。

两层锁：
- 壳协商锁（aps_runtime.lock）：锚定日志目录（bat / stop 链读取端合同），供启动器
  快速判断"是否已有实例"并给出归属提示；APS_LOG_DIR 等 env 分叉时两把壳锁互不可见。
- db-scope 排他锁（<db>.lock，B03）：锚定被保护资源（解析后的 DB 文件）所在路径，
  是同库双开的真互斥防线——同 db_path 才互斥，不同 db_path 的实例各自独立放行。

创建、陈旧回收、回滚、退出释放及契约清理共用短期 OS mutation guard。
guard 固定文件永不删除或截断，每次只保护一处锁的读取、归属判断与修改。
"""

from __future__ import annotations

import errno
import os
import sys
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional, Tuple, cast

from core.infrastructure.safe_files import (
    create_fixed_file_exclusive,
    open_fixed_file_for_write_binary,
    remove_fixed_file,
)
from web.runtime_host import normalize_runtime_db_path

from . import launcher_win32
from .launcher_lock_result import (
    LOCK_STATUS_MISSING,
    RuntimeLockReadResult,
    read_runtime_lock_result_from_path,
)
from .launcher_observability import launcher_log_warning
from .launcher_paths import (
    current_runtime_owner,
    db_scope_lock_path,
    resolve_runtime_state_dir,
    resolve_runtime_state_dir_for_read,
    runtime_lock_path,
)
from .launcher_processes import _pid_matches_contract, _pid_state, set_process_log_context


class RuntimeLockError(RuntimeError):
    pass


@contextmanager
def runtime_lock_mutation_guard(lock_path: str) -> Iterator[None]:
    """立即取得短期排他权；固定 guard 文件保留供所有后续调用使用。"""
    try:
        guard = open_fixed_file_for_write_binary(lock_path + ".guard", append=True)
    except OSError as exc:
        if isinstance(exc.__cause__, FileExistsError):
            raise RuntimeLockError("另一启动或退出操作正在处理运行锁，请稍后重试。") from exc
        raise RuntimeLockError(f"打开运行锁保护文件失败：{exc}") from exc
    with guard:
        fd = guard.fileno()
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            _change_mutation_guard_lock(fd, release=False)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise RuntimeLockError("另一启动或退出操作正在处理运行锁，请稍后重试。") from exc
            raise RuntimeLockError(f"取得运行锁修改权限失败：{exc}") from exc
        try:
            yield
        finally:
            os.lseek(fd, 0, os.SEEK_SET)
            _change_mutation_guard_lock(fd, release=True)


def _change_mutation_guard_lock(fd: int, *, release: bool) -> None:
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(fd, msvcrt.LK_UNLCK if release else msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN if release else fcntl.LOCK_EX | fcntl.LOCK_NB)


def _raise_uncertain_runtime_lock(result: RuntimeLockReadResult) -> None:
    launcher_log_warning(
        None,
        "检测到运行时锁但无法确认归属，跳过自动清理：path=%s status=%s reason=%s error=%s",
        result.path,
        result.status,
        result.reason,
        result.error,
        state_dir=result.state_dir,
    )
    raise RuntimeLockError("检测到运行时锁但无法确认归属，为避免重复启动或误删他人锁，请稍后重试。") from None


def is_runtime_lock_active(lock_payload: Dict[str, Any], expected_exe_path: str = "", *, local_probe_only: bool = False) -> bool:
    state_dir = str(lock_payload.get("state_dir") or "")
    set_process_log_context(state_dir=state_dir)
    pid = lock_payload["pid"]
    if local_probe_only and os.name == "nt":
        return _native_runtime_lock_active(pid, lock_payload, expected_exe_path)
    pid_state = _pid_state(pid)
    if pid_state is False:
        return False
    if pid_state is None:
        launcher_log_warning(None, "运行时锁 pid 状态无法确认，按仍可能活跃处理：pid=%s", pid, state_dir=str(lock_payload.get("state_dir") or ""))
        return True
    exe_path = str(lock_payload.get("exe_path") or expected_exe_path or "").strip()
    if exe_path:
        pid_match = _pid_matches_contract(pid, exe_path)
        if pid_match is False:
            return False
    return True


def _native_runtime_lock_active(pid: int, payload: Dict[str, Any], expected_exe_path: str) -> bool:
    if not launcher_win32.available():
        raise RuntimeLockError("本机原生进程探针不可用，运行锁归属未知，请稍后重试。")
    try:
        if not launcher_win32.pid_exists(pid):
            return False
        expected = str(payload.get("exe_path") or expected_exe_path or "").strip()
        if not expected:
            return True
        actual = launcher_win32.executable_path(pid)
        return bool(actual and os.path.normcase(os.path.abspath(actual)) == os.path.normcase(os.path.abspath(expected)))
    except OSError as exc:
        raise RuntimeLockError("本机原生进程探测失败，运行锁归属未知，请稍后重试。") from exc


def _runtime_lock_payload(owner: Optional[str], exe_path: Optional[str], db_path: Optional[str] = None) -> Dict[str, Any]:
    owner_s = str(owner or current_runtime_owner()).strip() or "unknown"
    exe_path_s = os.path.abspath(str(exe_path or sys.executable or "")).strip()
    payload: Dict[str, Any] = {
        "pid": int(os.getpid()),
        "owner": owner_s,
        "exe_path": exe_path_s,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    db_path_s = normalize_runtime_db_path(db_path)
    if db_path_s:
        # B03 方案丙补充：锁 payload 记录被保护的 DB 身份，供诊断与读取端核对
        #（bat 的 :read_lock_file 只取 owner/pid，多余键按合同被忽略）。
        payload["db_path"] = db_path_s
    return payload


def _create_new_runtime_lock(lock_path: str, payload: Dict[str, Any]) -> bool:
    try:
        fd = create_fixed_file_exclusive(lock_path)
    except FileExistsError:
        return False
    except Exception as e:
        raise RuntimeLockError(f"创建运行时锁失败：{e}") from e
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for key, value in payload.items():
                value_s = str(value if value is not None else "").replace("\r", " ").replace("\n", " ").strip()
                f.write(f"{key}={value_s}\n")
    except Exception:
        try:
            remove_fixed_file(lock_path)
        except Exception as cleanup_exc:
            launcher_log_warning(
                None,
                "创建运行时锁失败后清理锁文件失败，已继续抛出原错误：path=%s error=%s",
                lock_path,
                cleanup_exc,
                state_dir=os.path.dirname(lock_path),
            )
        raise
    return True


def _raise_if_runtime_lock_active(
    existing: Dict[str, Any],
    owner_s: str,
    exe_path_s: str,
    *,
    db_label: str = "",
) -> None:
    if not is_runtime_lock_active(existing, expected_exe_path=exe_path_s, local_probe_only=True):
        return
    existing_owner = str(existing.get("owner") or "").strip()
    if db_label:
        if existing_owner and existing_owner != owner_s:
            raise RuntimeLockError(
                f"数据库（{db_label}）当前正由 {existing_owner} 的实例使用，请等待其退出后再试。",
            ) from None
        raise RuntimeLockError(
            f"数据库（{db_label}）已被当前账户的另一实例使用，请直接使用现有窗口，不要重复启动。",
        ) from None
    if existing_owner and existing_owner != owner_s:
        raise RuntimeLockError(
            f"系统当前正由 {existing_owner} 使用，请等待其退出后再试。",
        ) from None
    raise RuntimeLockError(
        "系统已在当前账户运行，请直接使用现有窗口，不要重复启动。",
    ) from None


def lock_identity_fields(payload: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    return (
        str(payload.get("pid") or ""),
        str(payload.get("owner") or "").strip(),
        str(payload.get("exe_path") or "").strip(),
        str(payload.get("started_at") or "").strip(),
        str(payload.get("db_path") or "").strip(),
    )


def lock_process_identity_fields(payload: Dict[str, Any]) -> Tuple[str, str, str, str]:
    return (
        str(payload.get("pid") or ""),
        str(payload.get("owner") or "").strip(),
        normalize_runtime_db_path(payload.get("exe_path")),
        normalize_runtime_db_path(payload.get("db_path")),
    )


def _acquire_lock_file(
    lock_path: str,
    payload: Dict[str, Any],
    owner_s: str,
    exe_path_s: str,
    *,
    state_dir: str,
    db_label: str = "",
) -> Dict[str, Any]:
    with runtime_lock_mutation_guard(lock_path):
        existing_result = read_runtime_lock_result_from_path(lock_path, state_dir=state_dir)
        if existing_result.status != LOCK_STATUS_MISSING:
            if not existing_result.ok:
                _raise_uncertain_runtime_lock(existing_result)
            _raise_if_runtime_lock_active(cast(Dict[str, Any], existing_result.payload), owner_s, exe_path_s, db_label=db_label)
            try:
                remove_fixed_file(lock_path)
            except OSError as exc:
                raise RuntimeLockError(f"检测到失效运行时锁，但无法清理：{exc}") from exc
        if _create_new_runtime_lock(lock_path, payload):
            return payload
    raise RuntimeLockError("创建运行时锁失败，请稍后重试。")


def _acquire_db_scope_lock(db_path: str, *, owner_s: str, exe_path_s: str) -> Dict[str, Any]:
    lock_path = db_scope_lock_path(db_path)
    lock_dir = os.path.dirname(lock_path)
    os.makedirs(lock_dir, exist_ok=True)
    payload = _runtime_lock_payload(owner_s, exe_path_s, db_path=db_path)
    acquired = _acquire_lock_file(
        lock_path,
        payload,
        owner_s,
        exe_path_s,
        state_dir=lock_dir,
        db_label=normalize_runtime_db_path(db_path),
    )
    acquired["path"] = lock_path
    return acquired


def _rollback_own_runtime_lock(lock_path: str, own_payload: Dict[str, Any]) -> None:
    """db-scope 锁获取失败后回收本进程刚建立的壳锁（守卫式：只删仍是自己 payload 的锁）。
    回收失败只留痕不掩盖原错误——残留壳锁 pid 已死，会被下次启动按陈旧锁自愈。"""
    try:
        with runtime_lock_mutation_guard(lock_path):
            result = read_runtime_lock_result_from_path(lock_path)
            if result.status == LOCK_STATUS_MISSING:
                return
            removed = result.ok and lock_identity_fields(cast(Dict[str, Any], result.payload)) == lock_identity_fields(own_payload)
            if removed:
                remove_fixed_file(lock_path)
    except (RuntimeLockError, OSError) as exc:
        launcher_log_warning(
            None,
            "db 锁获取失败后回收壳锁失败，残留壳锁将由下次启动按陈旧锁自愈：path=%s error=%s",
            lock_path,
            exc,
            state_dir=os.path.dirname(lock_path),
        )
        return
    if not removed:
        launcher_log_warning(
            None,
            "db 锁获取失败后壳锁内容已非本进程所建，跳过回收：path=%s",
            lock_path,
            state_dir=os.path.dirname(lock_path),
        )


def acquire_runtime_lock(
    runtime_dir: str,
    cfg_log_dir: Optional[str] = None,
    *,
    owner: Optional[str] = None,
    exe_path: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    state_dir = resolve_runtime_state_dir(runtime_dir, cfg_log_dir)
    os.makedirs(state_dir, exist_ok=True)
    lock_path = runtime_lock_path(state_dir)
    payload = _runtime_lock_payload(owner, exe_path, db_path=db_path)
    owner_s = str(payload.get("owner") or "unknown")
    exe_path_s = str(payload.get("exe_path") or "")
    acquired = _acquire_lock_file(lock_path, payload, owner_s, exe_path_s, state_dir=state_dir)
    acquired["state_dir"] = state_dir
    acquired["path"] = lock_path
    db_path_s = str(db_path or "").strip()
    if not db_path_s:
        return acquired
    # B03 锁命名空间与被保护资源绑定（方案乙）：壳锁位置不动（bat/stop 读取端合同不破），
    # 在解析后的 DB 同路径追加 db-scope 排他锁作为同库双开的真互斥防线。
    try:
        acquired["db_lock"] = _acquire_db_scope_lock(db_path_s, owner_s=owner_s, exe_path_s=exe_path_s)
    except Exception:
        _rollback_own_runtime_lock(lock_path, acquired)
        raise
    return acquired


def _release_lock_from_result(
    result: RuntimeLockReadResult,
    expected_pid: Optional[int],
    *,
    expected_payload: Optional[Dict[str, Any]] = None,
) -> bool:
    if result.status == LOCK_STATUS_MISSING:
        return True
    if not result.ok:
        launcher_log_warning(
            None,
            "释放运行时锁时无法确认锁归属，跳过释放：path=%s status=%s reason=%s error=%s",
            result.path,
            result.status,
            result.reason,
            result.error,
            state_dir=result.state_dir,
        )
        return False
    existing = cast(Dict[str, Any], result.payload)
    if expected_payload is not None:
        if lock_identity_fields(existing) != lock_identity_fields(expected_payload):
            launcher_log_warning(None, "释放运行时锁时归属已变化，已保留当前实例锁：path=%s", result.path, state_dir=result.state_dir)
            return False
    pid0 = existing["pid"]
    state_dir = existing["state_dir"]
    if expected_pid is None and expected_payload is not None:
        expected_pid = expected_payload.get("pid")
    if expected_pid is None:
        pid_expected = int(os.getpid())
    else:
        try:
            pid_expected = int(expected_pid)
        except (TypeError, ValueError) as exc:
            launcher_log_warning(
                None,
                "释放运行时锁时 expected_pid 非法，跳过释放以避免误删他人锁：expected_pid=%r error=%s",
                expected_pid,
                exc,
                state_dir=state_dir,
            )
            return False
    if pid_expected <= 0:
        launcher_log_warning(None, "释放运行时锁时 expected_pid 非正，跳过释放：expected_pid=%s", pid_expected, state_dir=state_dir)
        return False
    if pid0 != pid_expected:
        return False
    try:
        remove_fixed_file(existing["path"])
    except FileNotFoundError:
        pass
    except OSError as exc:
        launcher_log_warning(None, "释放运行时锁失败，已继续：path=%s error=%s", existing["path"], exc, state_dir=state_dir)
        return False
    return True


def _release_lock_file(
    lock_path: str,
    expected_pid: Optional[int],
    *,
    state_dir: str,
    expected_payload: Optional[Dict[str, Any]],
) -> bool:
    try:
        with runtime_lock_mutation_guard(lock_path):
            return _release_lock_from_result(
                read_runtime_lock_result_from_path(lock_path, state_dir=state_dir),
                expected_pid,
                expected_payload=expected_payload,
            )
    except RuntimeLockError as exc:
        launcher_log_warning(None, "释放运行时锁失败：path=%s error=%s", lock_path, exc, state_dir=state_dir)
        return False


def release_runtime_lock(
    runtime_dir_or_state_dir: str,
    expected_pid: Optional[int] = None,
    db_path: Optional[str] = None,
    *,
    expected_payload: Optional[Dict[str, Any]] = None,
) -> bool:
    state_dir = resolve_runtime_state_dir_for_read(runtime_dir_or_state_dir)
    db_path_s = str(db_path or "").strip()
    db_lock_path = db_scope_lock_path(db_path_s) if db_path_s else ""
    expected_database = expected_payload.get("db_lock") if expected_payload is not None else None
    if db_path_s and expected_payload is not None and not isinstance(expected_database, dict):
        launcher_log_warning(None, "缺少原数据库锁身份，已保留数据库运行锁：path=%s", db_lock_path, state_dir=state_dir)
        return False
    shell_released = _release_lock_file(
        runtime_lock_path(state_dir),
        expected_pid,
        state_dir=state_dir,
        expected_payload=expected_payload,
    )
    if not db_path_s:
        return shell_released
    database_released = _release_lock_file(
        db_lock_path,
        expected_pid,
        state_dir=os.path.dirname(db_lock_path),
        expected_payload=expected_database,
    )
    return shell_released and database_released

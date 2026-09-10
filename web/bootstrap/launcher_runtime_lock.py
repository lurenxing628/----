"""运行时互斥锁生命周期（从 launcher_contracts 按职责拆出）。

两层锁：
- 壳协商锁（aps_runtime.lock）：锚定日志目录（bat / stop 链读取端合同），供启动器
  快速判断"是否已有实例"并给出归属提示；APS_LOG_DIR 等 env 分叉时两把壳锁互不可见。
- db-scope 排他锁（<db>.lock，B03）：锚定被保护资源（解析后的 DB 文件）所在路径，
  是同库双开的真互斥防线——同 db_path 才互斥，不同 db_path 的实例各自独立放行。

B02（陈旧锁读后删 TOCTOU）：删除陈旧锁前必须重读比对 payload，把"判定所依据的内容"
与"被删的内容"绑定，掐断并发双启动时 B 把 A 刚重建的新锁当陈旧锁删掉的路径。
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, Optional, Tuple

from core.infrastructure.safe_files import (
    create_fixed_file_exclusive,
    remove_fixed_file,
)

from .launcher_lock_result import (
    LOCK_STATUS_EMPTY,
    LOCK_STATUS_INVALID,
    LOCK_STATUS_MISSING,
    LOCK_STATUS_UNREADABLE,
    RuntimeLockReadResult,
    read_runtime_lock_result,
    read_runtime_lock_result_from_path,
)
from .launcher_observability import launcher_log_warning
from .launcher_paths import (
    _normalize_db_path_for_runtime,
    current_runtime_owner,
    db_scope_lock_path,
    resolve_runtime_state_dir,
    resolve_runtime_state_dir_for_read,
    runtime_lock_path,
)
from .launcher_processes import _pid_matches_contract, _pid_state, set_process_log_context


class RuntimeLockError(RuntimeError):
    def __init__(self, message: str, *, owner: str = "", pid: int = 0):
        super().__init__(message)
        self.owner = str(owner or "").strip()
        try:
            self.pid = int(pid or 0)
        except (TypeError, ValueError) as exc:
            launcher_log_warning(None, "解析运行时锁 pid 失败，已按 0 处理：pid=%r error=%s", pid, exc)
            self.pid = 0


def read_runtime_lock(runtime_dir_or_state_dir: str) -> Optional[Dict[str, Any]]:
    result = read_runtime_lock_result(runtime_dir_or_state_dir)
    return result.payload if result.ok else None


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


def _is_runtime_lock_active(lock_payload: Dict[str, Any], expected_exe_path: str = "") -> bool:
    if not isinstance(lock_payload, dict):
        return False
    state_dir = str(lock_payload.get("state_dir") or "")
    set_process_log_context(state_dir=state_dir)
    try:
        pid = int(lock_payload.get("pid") or 0)
    except (TypeError, ValueError) as exc:
        launcher_log_warning(None, "运行时锁 pid 非法，已按非活跃处理：%s", exc, state_dir=str(lock_payload.get("state_dir") or ""))
        pid = 0
    if pid <= 0:
        return False
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


def _runtime_lock_payload(owner: Optional[str], exe_path: Optional[str], db_path: Optional[str] = None) -> Dict[str, Any]:
    owner_s = str(owner or current_runtime_owner()).strip() or "unknown"
    exe_path_s = os.path.abspath(str(exe_path or sys.executable or "")).strip()
    payload: Dict[str, Any] = {
        "pid": int(os.getpid()),
        "owner": owner_s,
        "exe_path": exe_path_s,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    db_path_s = _normalize_db_path_for_runtime(db_path)
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
    if not _is_runtime_lock_active(existing, expected_exe_path=exe_path_s):
        return
    existing_owner = str(existing.get("owner") or "").strip()
    existing_pid = int(existing.get("pid") or 0)
    if db_label:
        if existing_owner and existing_owner != owner_s:
            raise RuntimeLockError(
                f"数据库（{db_label}）当前正由 {existing_owner} 的实例使用，请等待其退出后再试。",
                owner=existing_owner,
                pid=existing_pid,
            ) from None
        raise RuntimeLockError(
            f"数据库（{db_label}）已被当前账户的另一实例使用，请直接使用现有窗口，不要重复启动。",
            owner=existing_owner or owner_s,
            pid=existing_pid,
        ) from None
    if existing_owner and existing_owner != owner_s:
        raise RuntimeLockError(
            f"系统当前正由 {existing_owner} 使用，请等待其退出后再试。",
            owner=existing_owner,
            pid=existing_pid,
        ) from None
    raise RuntimeLockError(
        "系统已在当前账户运行，请直接使用现有窗口，不要重复启动。",
        owner=existing_owner or owner_s,
        pid=existing_pid,
    ) from None


def _lock_identity_fields(payload: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    data = payload or {}
    return (
        str(data.get("pid") or ""),
        str(data.get("owner") or "").strip(),
        str(data.get("exe_path") or "").strip(),
        str(data.get("started_at") or "").strip(),
        str(data.get("db_path") or "").strip(),
    )


def _remove_stale_runtime_lock(lock_path: str, expected_stale: Dict[str, Any]) -> bool:
    """陈旧锁删除守卫（B02 TOCTOU）：删除前重读锁文件，仅当内容仍是刚判定为陈旧的那份
    payload 才删除；返回 False 表示判定与删除之间锁已被并发替换（对方重建的新锁
    pid/started_at 必然不同），调用方必须放弃删除、按最新内容重新判定。
    重读与删除之间的窗口无法完全消除，但判定内容与被删内容绑定后，
    并发双启动时 B 删掉 A 新锁的路径被掐断。"""
    recheck = read_runtime_lock_result_from_path(lock_path)
    if recheck.status == LOCK_STATUS_MISSING:
        return True
    if not recheck.ok or _lock_identity_fields(recheck.payload or {}) != _lock_identity_fields(expected_stale):
        launcher_log_warning(
            None,
            "陈旧运行时锁在删除前已被并发替换，放弃删除并按最新内容重新判定：path=%s",
            lock_path,
            state_dir=os.path.dirname(lock_path),
        )
        return False
    try:
        remove_fixed_file(lock_path)
    except FileNotFoundError:
        pass
    except Exception as e:
        raise RuntimeLockError(f"检测到失效运行时锁，但无法清理：{e}") from e
    return True


def _acquire_lock_file(
    lock_path: str,
    payload: Dict[str, Any],
    owner_s: str,
    exe_path_s: str,
    *,
    state_dir: str,
    db_label: str = "",
) -> Dict[str, Any]:
    for _ in range(2):
        if _create_new_runtime_lock(lock_path, payload):
            return payload
        existing_result = read_runtime_lock_result_from_path(lock_path, state_dir=state_dir)
        if existing_result.status == LOCK_STATUS_MISSING:
            continue
        if existing_result.status in {LOCK_STATUS_EMPTY, LOCK_STATUS_UNREADABLE, LOCK_STATUS_INVALID}:
            time.sleep(0.15)
            existing_result = read_runtime_lock_result_from_path(lock_path, state_dir=state_dir)
        if not existing_result.ok:
            _raise_uncertain_runtime_lock(existing_result)
        existing = existing_result.payload or {}
        _raise_if_runtime_lock_active(existing, owner_s, exe_path_s, db_label=db_label)
        if not _remove_stale_runtime_lock(lock_path, existing):
            # B02：陈旧判定后锁内容已被并发替换（对方已重建新锁）——放弃删除，
            # 下一轮循环按新内容重新判定：活锁即拒启，绝不双实例上线。
            continue
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
        db_label=_normalize_db_path_for_runtime(db_path),
    )
    acquired["path"] = lock_path
    return acquired


def _rollback_own_runtime_lock(lock_path: str, own_payload: Dict[str, Any]) -> None:
    """db-scope 锁获取失败后回收本进程刚建立的壳锁（守卫式：只删仍是自己 payload 的锁）。
    回收失败只留痕不掩盖原错误——残留壳锁 pid 已死，会被下次启动按陈旧锁自愈。"""
    try:
        removed = _remove_stale_runtime_lock(lock_path, own_payload)
    except RuntimeLockError as exc:
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
        _acquire_db_scope_lock(db_path_s, owner_s=owner_s, exe_path_s=exe_path_s)
    except Exception:
        _rollback_own_runtime_lock(lock_path, acquired)
        raise
    return acquired


def _release_lock_from_result(
    result: RuntimeLockReadResult,
    expected_pid: Optional[int],
    *,
    fallback_state_dir: str,
) -> None:
    if result.status == LOCK_STATUS_MISSING:
        return
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
        return
    existing = result.payload or {}
    pid0 = int(existing.get("pid") or 0)
    state_dir = str(existing.get("state_dir") or fallback_state_dir)
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
            return
    if pid_expected <= 0:
        launcher_log_warning(None, "释放运行时锁时 expected_pid 非正，跳过释放：expected_pid=%s", pid_expected, state_dir=state_dir)
        return
    if pid0 > 0 and pid0 != pid_expected:
        return
    try:
        remove_fixed_file(str(existing.get("path") or ""))
    except FileNotFoundError:
        pass
    except (OSError, TypeError, ValueError) as exc:
        launcher_log_warning(None, "释放运行时锁失败，已继续：path=%s error=%s", existing.get("path"), exc, state_dir=state_dir)


def release_runtime_lock(
    runtime_dir_or_state_dir: str,
    expected_pid: Optional[int] = None,
    db_path: Optional[str] = None,
) -> None:
    _release_lock_from_result(
        read_runtime_lock_result(runtime_dir_or_state_dir),
        expected_pid,
        fallback_state_dir=resolve_runtime_state_dir_for_read(runtime_dir_or_state_dir),
    )
    db_path_s = str(db_path or "").strip()
    if not db_path_s:
        return
    db_lock_path = db_scope_lock_path(db_path_s)
    _release_lock_from_result(
        read_runtime_lock_result_from_path(db_lock_path),
        expected_pid,
        fallback_state_dir=os.path.dirname(db_lock_path),
    )

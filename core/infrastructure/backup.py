from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
import traceback
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator, Optional

from core.infrastructure.migrations.common import fallback_log

_MAINT_MUTEX = threading.RLock()
_MAINT_CONTEXT = threading.local()
_MAINT_LOCK_STALE_SECONDS = 300


class MaintenanceWindowError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = str(code or "").strip() or "maintenance_error"
        self.message = str(message or "数据库正在维护/恢复中，请稍后重试。")
        super().__init__(self.message)


@dataclass(frozen=True)
class RestoreResult:
    ok: bool
    code: str
    message: str
    before_restore_path: Optional[str] = None


def _maintenance_lock_path(db_path: str) -> str:
    return os.path.abspath(db_path) + ".maintenance.lock"


def _current_maintenance_state() -> Optional[dict]:
    state = getattr(_MAINT_CONTEXT, "state", None)
    if isinstance(state, dict):
        return state
    return None


def current_thread_holds_maintenance_window(db_path: str) -> bool:
    state = _current_maintenance_state()
    return bool(state and state.get("db_path") == os.path.abspath(db_path) and int(state.get("depth") or 0) > 0)


def _pid_exists(pid: Optional[int]) -> bool:
    try:
        pid_int = int(pid or 0)
    except Exception:
        return True
    if pid_int <= 0:
        return True
    if os.name == "nt":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid_int)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            err = int(ctypes.windll.kernel32.GetLastError() or 0)
            if err == 5:
                return True
            return False
        except Exception:
            return True
    try:
        os.kill(pid_int, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return True
    return True


def _empty_maintenance_lock_state(lock_path: str) -> dict:
    state = {"path": lock_path, "pid": None, "action": None, "ts": None, "age_seconds": None, "raw": ""}
    return state


def _read_lock_file_text(lock_path: str, state: dict) -> Optional[str]:
    try:
        with open(lock_path, "rb") as f:
            raw = f.read().decode("utf-8", errors="ignore").strip()
    except Exception as e:
        state["read_error"] = e
        return None
    return raw


def _apply_maintenance_lock_token(state: dict, token: str) -> None:
    if "=" not in token:
        return
    key, value = token.split("=", 1)
    key = str(key or "").strip().lower()
    value = str(value or "").strip()
    if key == "pid":
        try:
            state["pid"] = int(value)
        except Exception:
            state["pid"] = None
    elif key == "action":
        state["action"] = value or None
    elif key == "ts":
        state["ts_text"] = value or None
        try:
            state["ts"] = datetime.fromisoformat(value)
        except Exception:
            state["ts"] = None


def _apply_maintenance_lock_age(state: dict) -> None:
    ts = state.get("ts")
    if not isinstance(ts, datetime):
        return
    try:
        state["age_seconds"] = max(0.0, (datetime.now() - ts).total_seconds())
    except Exception:
        state["age_seconds"] = None


def read_maintenance_lock_state(db_path: str) -> Optional[dict]:
    lock_path = _maintenance_lock_path(db_path)
    if not os.path.exists(lock_path):
        return None
    state = _empty_maintenance_lock_state(lock_path)
    raw = _read_lock_file_text(lock_path, state)
    if raw is None:
        return state
    state["raw"] = raw
    for token in raw.split():
        _apply_maintenance_lock_token(state, token)
    _apply_maintenance_lock_age(state)
    return state


def _should_auto_heal_lock(state: Optional[dict]) -> bool:
    if not isinstance(state, dict):
        return False
    age_seconds = state.get("age_seconds")
    if age_seconds is None:
        return False
    try:
        age_value = float(age_seconds)
    except Exception:
        return False
    if age_value < float(_MAINT_LOCK_STALE_SECONDS):
        return False
    return not _pid_exists(state.get("pid"))


def is_maintenance_window_active(db_path: str, *, logger=None) -> bool:
    if current_thread_holds_maintenance_window(db_path):
        return True
    try:
        state = read_maintenance_lock_state(db_path)
        if state is None:
            return False
        if _should_auto_heal_lock(state):
            lock_path = str(state.get("path") or _maintenance_lock_path(db_path))
            try:
                os.remove(lock_path)
                fallback_log(
                    logger,
                    "warning",
                    f"检测到陈旧维护锁，已自动清理：{lock_path}（pid={state.get('pid')} age_s={int(state.get('age_seconds') or 0)}）",
                )
                return False
            except Exception as e:
                fallback_log(logger, "warning", f"陈旧维护锁自动清理失败：{e}（path={lock_path}）")
        return True
    except Exception as exc:
        fallback_log(logger, "warning", f"维护锁状态检测失败，已按不可确认处理并阻止继续：{exc}")
        raise MaintenanceWindowError("lock_state_unavailable", "系统维护锁状态检测失败，请稍后重试。") from exc


def ensure_backup_allowed(db_path: str, *, logger=None) -> None:
    if current_thread_holds_maintenance_window(db_path):
        return
    if is_maintenance_window_active(db_path, logger=logger):
        raise MaintenanceWindowError("busy", "数据库正在维护/恢复中，请稍后重试。")


def _enter_nested_maintenance_window(state: dict, db_abs: str) -> None:
    if state.get("db_path") != db_abs:
        raise MaintenanceWindowError("busy", "当前线程已有其他维护任务在执行，暂不支持跨数据库嵌套维护。")
    state["depth"] = int(state.get("depth") or 0) + 1


def _exit_nested_maintenance_window(state: dict) -> None:
    state["depth"] = max(0, int(state.get("depth") or 1) - 1)


def _acquire_maintenance_mutex() -> None:
    if not _MAINT_MUTEX.acquire(blocking=False):
        raise MaintenanceWindowError("busy", "数据库正在维护/恢复中，请稍后重试。")


@contextmanager
def maintenance_window(db_path: str, *, logger=None, action: str = "maintenance") -> Iterator[None]:
    db_abs = os.path.abspath(db_path)
    state = _current_maintenance_state()
    if state is not None:
        _enter_nested_maintenance_window(state, db_abs)
        try:
            yield
        finally:
            _exit_nested_maintenance_window(state)
        return

    _acquire_maintenance_mutex()

    lock_path = _maintenance_lock_path(db_abs)
    lock_fd = None
    entered_root = False
    try:
        if is_maintenance_window_active(db_abs, logger=logger):
            raise MaintenanceWindowError("busy", "数据库正在维护/恢复中，请稍后重试。")
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(lock_fd, f"pid={os.getpid()} action={action} ts={datetime.now().isoformat()}".encode())
            except Exception:
                pass
        except FileExistsError as e:
            raise MaintenanceWindowError("busy", "数据库正在维护/恢复中，请稍后重试。") from e
        except Exception as e:
            raise MaintenanceWindowError("lock_failed", f"维护锁文件创建失败：{e}") from e

        _MAINT_CONTEXT.state = {"db_path": db_abs, "depth": 1, "lock_path": lock_path, "lock_fd": lock_fd}
        entered_root = True
        yield
    finally:
        if entered_root:
            try:
                delattr(_MAINT_CONTEXT, "state")
            except Exception:
                try:
                    _MAINT_CONTEXT.state = None
                except Exception:
                    pass
            if lock_fd is not None:
                try:
                    os.close(lock_fd)
                except Exception as e:
                    fallback_log(logger, "warning", f"维护锁文件句柄关闭失败：{e}")
            try:
                if os.path.exists(lock_path):
                    os.remove(lock_path)
            except Exception as e:
                fallback_log(logger, "warning", f"维护锁文件删除失败：{e}")
        try:
            _MAINT_MUTEX.release()
        except Exception:
            pass


class BackupManager:
    """数据库备份管理器（退出自动备份 + 手动备份/恢复/清理）。"""

    def __init__(
        self,
        db_path: str,
        backup_dir: str = "backups",
        keep_days: int = 7,
        logger: Optional[logging.Logger] = None,
    ):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.keep_days = keep_days
        self.logger = logger or logging.getLogger(__name__)

        os.makedirs(backup_dir, exist_ok=True)

    def backup(self, suffix: Optional[str] = None) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix_str = f"_{suffix}" if suffix else ""
        backup_name = f"aps_backup_{timestamp}{suffix_str}.db"
        backup_path = os.path.join(self.backup_dir, backup_name)
        tmp_path = backup_path + ".tmp"

        try:
            with maintenance_window(self.db_path, logger=self.logger, action="backup"):
                # 先写入临时文件，成功后原子替换，避免留下半成品备份文件
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass

                # 两次 connect 任一失败都必须确保已打开的连接能关闭（避免句柄泄漏）
                with closing(sqlite3.connect(self.db_path)) as source:
                    with closing(sqlite3.connect(tmp_path)) as dest:
                        source.backup(dest)

                        # 备份后完整性校验（建议启用；失败则不生成最终备份文件）
                        try:
                            rows = dest.execute("PRAGMA integrity_check").fetchall() or []
                        except Exception as e:
                            # 校验执行失败：不阻断备份，但记录 warning 便于排障
                            fallback_log(self.logger, "warning", f"备份 integrity_check 执行失败（已忽略）：{e}")
                        else:
                            msg0 = str((rows[0][0] if rows else "") or "").strip().lower()
                            if msg0 != "ok":
                                fallback_log(self.logger, "error", f"备份 integrity_check 未通过：{rows}")
                                raise RuntimeError(f"backup integrity_check failed: {rows}")
                os.replace(tmp_path, backup_path)
                fallback_log(self.logger, "info", f"数据库已备份：{backup_path}")
                return backup_path
        finally:
            # 异常路径清理临时文件（最佳努力）
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    def _copy_db_file(self, source_path: str, *, locked_warning_message: str) -> None:
        retries = 6
        for i in range(retries):
            try:
                with closing(sqlite3.connect(source_path)) as source:
                    with closing(sqlite3.connect(self.db_path, timeout=30)) as dest:
                        try:
                            dest.execute("PRAGMA busy_timeout = 30000")
                        except Exception:
                            pass
                        source.backup(dest)
                return
            except sqlite3.OperationalError as exc:
                message = str(exc).lower()
                if ("locked" in message or "busy" in message) and i < retries - 1:
                    fallback_log(self.logger, "warning", f"{locked_warning_message}：{exc}")
                    time.sleep(0.2 * (i + 1))
                    continue
                raise

    def _auto_rollback(
        self,
        before_restore_path: Optional[str],
        *,
        failure_subject: str,
        rolled_back_code: str,
        rollback_failed_code: str,
    ) -> Optional[RestoreResult]:
        if not before_restore_path or not os.path.exists(before_restore_path):
            fallback_log(self.logger, "error", f"{failure_subject}，但缺少恢复前快照，无法自动回滚。")
            return None

        try:
            self._copy_db_file(before_restore_path, locked_warning_message="自动回滚时数据库被占用，准备重试")
        except Exception:
            fallback_log(self.logger, "error", f"{failure_subject}且自动回滚失败\n{traceback.format_exc()}")
            return RestoreResult(
                ok=False,
                code=rollback_failed_code,
                message=f"{failure_subject}，且自动回滚也失败了，请立即检查日志并手动校验数据库。",
                before_restore_path=before_restore_path,
            )

        snapshot_name = os.path.basename(before_restore_path)
        fallback_log(self.logger, "error", f"{failure_subject}，已自动回滚到恢复前备份：{before_restore_path}")
        return RestoreResult(
            ok=False,
            code=rolled_back_code,
            message=f"{failure_subject}，但已自动回滚到恢复前备份：{snapshot_name}。",
            before_restore_path=before_restore_path,
        )

    def restore(self, backup_path: str) -> RestoreResult:
        if not os.path.exists(backup_path):
            fallback_log(self.logger, "error", f"备份文件不存在：{backup_path}")
            return RestoreResult(ok=False, code="backup_missing", message=f"备份文件不存在：{backup_path}")

        before_restore_path = None
        try:
            with maintenance_window(self.db_path, logger=self.logger, action="restore"):
                # 恢复前自动备份
                before_restore_path = self.backup(suffix="before_restore")

                self._copy_db_file(backup_path, locked_warning_message="数据库被占用（可能有其它连接未释放），准备重试")
                fallback_log(self.logger, "info", f"数据库文件复制完成，等待后续结构校验：{backup_path}")
                return RestoreResult(
                    ok=True,
                    code="copied_pending_verify",
                    message=f"数据库文件已复制，等待后续结构校验：{backup_path}",
                    before_restore_path=before_restore_path,
                )
        except MaintenanceWindowError as e:
            fallback_log(self.logger, "warning" if e.code == "busy" else "error", e.message)
            return RestoreResult(ok=False, code=e.code, message=e.message)
        except Exception:
            fallback_log(self.logger, "error", f"数据库恢复失败\n{traceback.format_exc()}")
            rollback_result = self._auto_rollback(
                before_restore_path,
                failure_subject="数据库恢复失败",
                rolled_back_code="restore_failed_rolled_back",
                rollback_failed_code="restore_failed_rollback_failed",
            )
            if rollback_result is not None:
                return rollback_result
            return RestoreResult(
                ok=False,
                code="restore_failed",
                message="数据库恢复失败，请查看日志。",
                before_restore_path=before_restore_path,
            )
        return RestoreResult(
            ok=False,
            code="restore_failed",
            message="数据库恢复失败，请查看日志。",
            before_restore_path=before_restore_path,
        )

    def cleanup_old_backups(self):
        cutoff = datetime.now() - timedelta(days=self.keep_days)
        if not os.path.exists(self.backup_dir):
            return

        for filename in os.listdir(self.backup_dir):
            if not filename.startswith("aps_backup_"):
                continue

            filepath = os.path.join(self.backup_dir, filename)
            try:
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if file_time < cutoff:
                    os.remove(filepath)
                    fallback_log(self.logger, "info", f"已清理过期备份：{filename}")
            except Exception as e:
                fallback_log(self.logger, "warning", f"清理备份失败（{filename}）：{e}")

    def list_backups(self) -> list:
        backups = []
        if not os.path.exists(self.backup_dir):
            return backups

        for filename in sorted(os.listdir(self.backup_dir), reverse=True):
            if not filename.startswith("aps_backup_"):
                continue

            filepath = os.path.join(self.backup_dir, filename)
            stat = os.stat(filepath)
            backups.append(
                {
                    "filename": filename,
                    "path": filepath,
                    "size_mb": round(stat.st_size / 1024 / 1024, 2),
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
        return backups

from __future__ import annotations

import getpass
import ntpath
import os
import sys
from typing import Any, Dict, Optional

RUNTIME_CONTRACT_VERSION = 1
RUNTIME_SHUTDOWN_PATH = "/system/runtime/shutdown"
RUNTIME_LOCK_FILE = "aps_runtime.lock"
RUNTIME_ERROR_FILE = "aps_launch_error.txt"


def _normalize_db_path_for_runtime(db_path: str | None) -> str:
    raw = str(db_path or "").strip()
    if not raw:
        return ""
    return os.path.normcase(os.path.abspath(raw))


def _normalize_abs_dir(path: str | None) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    return os.path.abspath(raw)


def _compose_runtime_owner(user: str | None, domain: str | None) -> str:
    user_s = str(user or "").strip()
    domain_s = str(domain or "").strip()
    if domain_s and user_s and domain_s.lower() != user_s.lower():
        return f"{domain_s}\\{user_s}"
    return user_s or domain_s or "unknown"


def current_runtime_owner() -> str:
    user = str(os.environ.get("USERNAME") or "").strip()
    if not user:
        try:
            user = str(getpass.getuser() or "").strip()
        except Exception:
            user = ""
    domain = str(os.environ.get("USERDOMAIN") or os.environ.get("COMPUTERNAME") or "").strip()
    return _compose_runtime_owner(user, domain)


def read_shared_data_root_from_registry() -> str:
    try:
        import winreg  # type: ignore
    except ImportError:
        return ""
    key_read = int(getattr(winreg, "KEY_READ", 0))
    wow64_64 = int(getattr(winreg, "KEY_WOW64_64KEY", 0))
    open_key: Any = getattr(winreg, "OpenKey", None)
    query_value_ex: Any = getattr(winreg, "QueryValueEx", None)
    close_key: Any = getattr(winreg, "CloseKey", None)
    hkey_local_machine: Any = getattr(winreg, "HKEY_LOCAL_MACHINE", None)
    if not callable(open_key) or not callable(query_value_ex) or not callable(close_key) or hkey_local_machine is None:
        return ""
    for access in (key_read | wow64_64, key_read):
        try:
            key = open_key(hkey_local_machine, r"SOFTWARE\APS", 0, access)
        except Exception:
            continue
        try:
            result = query_value_ex(key, "SharedDataRoot")
            value = result[0] if isinstance(result, tuple) and result else ""
        except Exception:
            value = ""
        finally:
            try:
                close_key(key)
            except Exception:
                pass
        shared_root = _normalize_abs_dir(value)
        if shared_root:
            return shared_root
    return ""


def resolve_shared_data_root(base_dir: str, *, frozen: Optional[bool] = None) -> str:
    explicit_root = _normalize_abs_dir(os.environ.get("APS_SHARED_DATA_ROOT"))
    if explicit_root:
        return explicit_root
    base_dir_abs = _normalize_abs_dir(base_dir) or os.path.abspath(str(base_dir or "."))
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    if not is_frozen:
        return base_dir_abs
    registry_root = read_shared_data_root_from_registry()
    if registry_root:
        return registry_root
    program_data = _normalize_abs_dir(os.environ.get("ProgramData"))
    if program_data:
        candidate = os.path.join(program_data, "APS", "shared-data")
        if os.path.isdir(candidate):
            return candidate
    return base_dir_abs


def resolve_prelaunch_log_dir(runtime_dir: str, *, frozen: Optional[bool] = None) -> str:
    explicit_log_dir = _normalize_abs_dir(os.environ.get("APS_LOG_DIR"))
    if explicit_log_dir:
        return explicit_log_dir
    return os.path.join(resolve_shared_data_root(runtime_dir, frozen=frozen), "logs")


def runtime_log_dir(runtime_dir: str) -> str:
    return os.path.join(str(runtime_dir), "logs")


def resolve_runtime_state_dir(runtime_dir: str, cfg_log_dir: str | None = None) -> str:
    cfg_log_dir_s = ""
    try:
        cfg_log_dir_s = str(cfg_log_dir).strip() if cfg_log_dir is not None else ""
    except Exception:
        cfg_log_dir_s = ""
    if cfg_log_dir_s:
        return os.path.abspath(cfg_log_dir_s)
    return os.path.abspath(runtime_log_dir(runtime_dir))


def resolve_runtime_state_dir_for_read(runtime_dir_or_state_dir: str) -> str:
    base = os.path.abspath(str(runtime_dir_or_state_dir))
    if os.path.basename(base).strip().lower() == "logs":
        return base
    direct_files = [
        "aps_host.txt",
        "aps_port.txt",
        "aps_db_path.txt",
        "aps_runtime.json",
        RUNTIME_LOCK_FILE,
        RUNTIME_ERROR_FILE,
    ]
    if any(os.path.exists(os.path.join(base, name)) for name in direct_files):
        return base
    return os.path.join(base, "logs")


def runtime_dir_from_state_dir(state_dir: str) -> str:
    state_dir_abs = os.path.abspath(str(state_dir or ""))
    if os.path.basename(state_dir_abs).strip().lower() == "logs":
        parent_dir = os.path.dirname(state_dir_abs)
        if parent_dir:
            return parent_dir
    return state_dir_abs


def resolve_runtime_stop_context(runtime_dir_or_state_dir: str) -> tuple[str, str]:
    raw_path = os.path.abspath(str(runtime_dir_or_state_dir))
    state_dir = resolve_runtime_state_dir_for_read(raw_path)
    if os.path.normcase(raw_path) == os.path.normcase(state_dir):
        runtime_dir = runtime_dir_from_state_dir(state_dir)
    else:
        runtime_dir = raw_path
    return runtime_dir, state_dir


def runtime_log_mirror_dir(runtime_dir: str, cfg_log_dir: str | None = None) -> str:
    repo_log_dir = os.path.abspath(runtime_log_dir(runtime_dir))
    state_dir = resolve_runtime_state_dir(runtime_dir, cfg_log_dir)
    if os.path.normcase(repo_log_dir) == os.path.normcase(state_dir):
        return ""
    return repo_log_dir


def state_contract_paths(state_dir: str) -> tuple[str, str, str, str]:
    return (
        os.path.join(state_dir, "aps_host.txt"),
        os.path.join(state_dir, "aps_port.txt"),
        os.path.join(state_dir, "aps_db_path.txt"),
        os.path.join(state_dir, "aps_runtime.json"),
    )


def runtime_lock_path(state_dir: str) -> str:
    return os.path.join(state_dir, RUNTIME_LOCK_FILE)


def launch_error_path(state_dir: str) -> str:
    return os.path.join(state_dir, RUNTIME_ERROR_FILE)


def resolve_runtime_state_paths(runtime_dir_or_state_dir: str) -> Dict[str, str]:
    """返回运行态状态文件的规范路径集合。"""

    state_dir = resolve_runtime_state_dir_for_read(runtime_dir_or_state_dir)
    runtime_dir = runtime_dir_from_state_dir(state_dir)
    host_path, port_path, db_path, contract_path = state_contract_paths(state_dir)
    return {
        "runtime_dir": runtime_dir,
        "state_dir": state_dir,
        "host_path": host_path,
        "port_path": port_path,
        "db_path": db_path,
        "contract_path": contract_path,
        "lock_path": runtime_lock_path(state_dir),
        "error_path": launch_error_path(state_dir),
    }


def default_chrome_profile_dir(runtime_dir: str) -> str:
    local_appdata = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local_appdata:
        if "\\" in local_appdata and "/" not in local_appdata:
            return os.path.abspath(ntpath.join(local_appdata, "APS", "Chrome109Profile"))
        return os.path.abspath(os.path.join(local_appdata, "APS", "Chrome109Profile"))
    return os.path.abspath(os.path.join(str(runtime_dir), "chrome109_profile"))

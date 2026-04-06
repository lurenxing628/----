from __future__ import annotations

import getpass
import ipaddress
import json
import logging
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

_RUNTIME_CONTRACT_VERSION = 1
_RUNTIME_SHUTDOWN_PATH = "/system/runtime/shutdown"
_RUNTIME_LOCK_FILE = "aps_runtime.lock"
_RUNTIME_ERROR_FILE = "aps_launch_error.txt"


def pick_bind_host(raw_host: str | None, *, logger: logging.Logger | None = None) -> str:
    host = (raw_host or "").strip() or "127.0.0.1"
    try:
        ip = ipaddress.ip_address(host)
        if getattr(ip, "version", None) != 4:
            raise ValueError("not ipv4")
    except Exception:
        if logger is not None:
            try:
                logger.warning(f"APS_HOST 非法或非 IPv4：{host}，已回退到 127.0.0.1")
            except Exception:
                pass
        host = "127.0.0.1"
    return host


def _can_bind(host0: str, port0: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        s.bind((host0, int(port0)))
        return True
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def pick_port(host: str, preferred: int, *, logger: logging.Logger | None = None) -> tuple[str, int]:
    candidates: list[int] = []
    for p in [preferred, 5000, 5705, 5706, 5707, 5710, 5711, 5712, 5713, 5714, 5715]:
        try:
            p0 = int(p)
        except Exception:
            continue
        if p0 <= 0:
            continue
        if p0 not in candidates:
            candidates.append(p0)

    fallback_host = "127.0.0.1"
    for p in candidates:
        if _can_bind(host, p):
            return (host, int(p))

    if host != fallback_host:
        for p in candidates:
            if _can_bind(fallback_host, p):
                return (fallback_host, int(p))

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        try:
            s.bind((host, 0))
            _h, p = s.getsockname()
            return (host, int(p))
        except Exception:
            s.close()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind((fallback_host, 0))
            _h, p = s.getsockname()
            return (fallback_host, int(p))
    finally:
        try:
            s.close()
        except Exception:
            pass


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
    for access in (key_read | wow64_64, key_read):
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\APS", 0, access)
        except Exception:
            continue
        try:
            value, _value_type = winreg.QueryValueEx(key, "SharedDataRoot")
        except Exception:
            value = ""
        finally:
            try:
                winreg.CloseKey(key)
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


def _runtime_log_dir(runtime_dir: str) -> str:
    return os.path.join(str(runtime_dir), "logs")


def resolve_runtime_state_dir(runtime_dir: str, cfg_log_dir: str | None = None) -> str:
    cfg_log_dir_s = ""
    try:
        cfg_log_dir_s = str(cfg_log_dir).strip() if cfg_log_dir is not None else ""
    except Exception:
        cfg_log_dir_s = ""
    if cfg_log_dir_s:
        return os.path.abspath(cfg_log_dir_s)
    return os.path.abspath(_runtime_log_dir(runtime_dir))


def _resolve_runtime_state_dir_for_read(runtime_dir_or_state_dir: str) -> str:
    base = os.path.abspath(str(runtime_dir_or_state_dir))
    if os.path.basename(base).strip().lower() == "logs":
        return base
    direct_files = [
        "aps_host.txt",
        "aps_port.txt",
        "aps_db_path.txt",
        "aps_runtime.json",
        _RUNTIME_LOCK_FILE,
        _RUNTIME_ERROR_FILE,
    ]
    if any(os.path.exists(os.path.join(base, name)) for name in direct_files):
        return base
    return os.path.join(base, "logs")


def _runtime_dir_from_state_dir(state_dir: str) -> str:
    state_dir_abs = os.path.abspath(str(state_dir or ""))
    if os.path.basename(state_dir_abs).strip().lower() == "logs":
        parent_dir = os.path.dirname(state_dir_abs)
        if parent_dir:
            return parent_dir
    return state_dir_abs


def _resolve_runtime_stop_context(runtime_dir_or_state_dir: str) -> tuple[str, str]:
    raw_path = os.path.abspath(str(runtime_dir_or_state_dir))
    state_dir = _resolve_runtime_state_dir_for_read(raw_path)
    if os.path.normcase(raw_path) == os.path.normcase(state_dir):
        runtime_dir = _runtime_dir_from_state_dir(state_dir)
    else:
        runtime_dir = raw_path
    return runtime_dir, state_dir


def _runtime_log_mirror_dir(runtime_dir: str, cfg_log_dir: str | None = None) -> str:
    runtime_log_dir = os.path.abspath(_runtime_log_dir(runtime_dir))
    state_dir = resolve_runtime_state_dir(runtime_dir, cfg_log_dir)
    if os.path.normcase(runtime_log_dir) == os.path.normcase(state_dir):
        return ""
    return runtime_log_dir


def _state_contract_paths(state_dir: str) -> tuple[str, str, str, str]:
    return (
        os.path.join(state_dir, "aps_host.txt"),
        os.path.join(state_dir, "aps_port.txt"),
        os.path.join(state_dir, "aps_db_path.txt"),
        os.path.join(state_dir, "aps_runtime.json"),
    )


def _runtime_lock_path(state_dir: str) -> str:
    return os.path.join(state_dir, _RUNTIME_LOCK_FILE)


def _launch_error_path(state_dir: str) -> str:
    return os.path.join(state_dir, _RUNTIME_ERROR_FILE)


def _write_runtime_state_triplet(state_dir: str, host: str, port: int, db_for_runtime: str) -> None:
    host_file, port_file, db_file, _contract_file = _state_contract_paths(state_dir)
    with open(port_file, "w", encoding="utf-8") as f:
        f.write(str(int(port)) + "\n")
    host_for_client = (str(host or "").strip() or "127.0.0.1")
    if host_for_client == "0.0.0.0":
        host_for_client = "127.0.0.1"
    with open(host_file, "w", encoding="utf-8") as f:
        f.write(str(host_for_client) + "\n")
    with open(db_file, "w", encoding="utf-8") as f:
        f.write(db_for_runtime + "\n")


def _write_key_value_file(path: str, data: Dict[str, Any]) -> None:
    lines = []
    for key, value in (data or {}).items():
        key_s = str(key or "").strip()
        if not key_s:
            continue
        value_s = str(value if value is not None else "").replace("\r", " ").replace("\n", " ").strip()
        lines.append(f"{key_s}={value_s}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


def _read_key_value_file(path: str) -> Dict[str, str]:
    if not os.path.exists(path):
        return {}
    data: Dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return {}
    for raw in lines:
        line = str(raw or "").strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key_s = str(key or "").strip()
        if not key_s:
            continue
        data[key_s] = str(value or "").strip()
    return data


def _pid_exists(pid: int) -> bool:
    try:
        pid_i = int(pid)
    except Exception:
        return False
    if pid_i <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid_i}", "/NH", "/FO", "CSV"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except Exception:
            return False
        for line in (result.stdout or "").splitlines():
            line_s = str(line or "").strip()
            if line_s.startswith('"') and f',"{pid_i}",' in line_s:
                return True
        return False
    try:
        os.kill(pid_i, 0)
        return True
    except Exception:
        return False


class RuntimeLockError(RuntimeError):
    def __init__(self, message: str, *, owner: str = "", pid: int = 0):
        super().__init__(message)
        self.owner = str(owner or "").strip()
        try:
            self.pid = int(pid or 0)
        except Exception:
            self.pid = 0


def read_runtime_lock(runtime_dir_or_state_dir: str) -> Optional[Dict[str, Any]]:
    state_dir = _resolve_runtime_state_dir_for_read(runtime_dir_or_state_dir)
    lock_path = _runtime_lock_path(state_dir)
    if not os.path.exists(lock_path):
        return None
    payload = _read_key_value_file(lock_path)
    if not payload:
        return None
    try:
        payload["pid"] = int(payload.get("pid") or 0)
    except Exception:
        payload["pid"] = 0
    payload["state_dir"] = state_dir
    payload["path"] = lock_path
    return payload


def _is_runtime_lock_active(lock_payload: Dict[str, Any], expected_exe_path: str = "") -> bool:
    if not isinstance(lock_payload, dict):
        return False
    try:
        pid = int(lock_payload.get("pid") or 0)
    except Exception:
        pid = 0
    if pid <= 0 or not _pid_exists(pid):
        return False
    exe_path = str(lock_payload.get("exe_path") or expected_exe_path or "").strip()
    if exe_path:
        pid_match = _pid_matches_contract(pid, exe_path)
        if pid_match is False:
            return False
    return True


def acquire_runtime_lock(
    runtime_dir: str,
    cfg_log_dir: str | None = None,
    *,
    owner: str | None = None,
    exe_path: str | None = None,
) -> Dict[str, Any]:
    state_dir = resolve_runtime_state_dir(runtime_dir, cfg_log_dir)
    os.makedirs(state_dir, exist_ok=True)
    lock_path = _runtime_lock_path(state_dir)
    owner_s = str(owner or current_runtime_owner()).strip() or "unknown"
    exe_path_s = os.path.abspath(str(exe_path or sys.executable or "")).strip()
    payload: Dict[str, Any] = {
        "pid": int(os.getpid()),
        "owner": owner_s,
        "exe_path": exe_path_s,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    for _ in range(2):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            existing = read_runtime_lock(state_dir) or {}
            if _is_runtime_lock_active(existing, expected_exe_path=exe_path_s):
                existing_owner = str(existing.get("owner") or "").strip()
                existing_pid = int(existing.get("pid") or 0)
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
            try:
                os.remove(lock_path)
            except FileNotFoundError:
                pass
            except Exception as e:
                raise RuntimeLockError(f"检测到失效运行时锁，但无法清理：{e}") from e
            continue
        except Exception as e:
            raise RuntimeLockError(f"创建运行时锁失败：{e}") from e
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for key, value in payload.items():
                    value_s = str(value if value is not None else "").replace("\r", " ").replace("\n", " ").strip()
                    f.write(f"{key}={value_s}\n")
        except Exception:
            try:
                os.remove(lock_path)
            except Exception:
                pass
            raise
        payload["state_dir"] = state_dir
        payload["path"] = lock_path
        return payload
    raise RuntimeLockError("创建运行时锁失败，请稍后重试。")


def release_runtime_lock(runtime_dir_or_state_dir: str, expected_pid: int | None = None) -> None:
    existing = read_runtime_lock(runtime_dir_or_state_dir)
    if not existing:
        return
    pid0 = int(existing.get("pid") or 0)
    pid_expected = 0
    try:
        pid_expected = int(expected_pid if expected_pid is not None else os.getpid())
    except Exception:
        pid_expected = 0
    if pid_expected > 0 and pid0 > 0 and pid0 != pid_expected:
        return
    try:
        os.remove(str(existing.get("path") or ""))
    except FileNotFoundError:
        pass
    except Exception:
        pass


def write_launch_error(runtime_dir: str, message: str, cfg_log_dir: str | None = None) -> str:
    state_dir = resolve_runtime_state_dir(runtime_dir, cfg_log_dir)
    os.makedirs(state_dir, exist_ok=True)
    error_path = _launch_error_path(state_dir)
    with open(error_path, "w", encoding="utf-8") as f:
        f.write((str(message or "").strip() or "应用启动失败。") + "\n")
    return error_path


def clear_launch_error(runtime_dir_or_state_dir: str) -> None:
    state_dir = _resolve_runtime_state_dir_for_read(runtime_dir_or_state_dir)
    error_path = _launch_error_path(state_dir)
    try:
        os.remove(error_path)
    except FileNotFoundError:
        pass
    except Exception:
        pass


def write_runtime_host_port_files(
    runtime_dir: str,
    cfg_log_dir: str | None,
    host: str,
    port: int,
    db_path: str | None = None,
    *,
    logger: logging.Logger | None = None,
) -> None:
    db_for_runtime = _normalize_db_path_for_runtime(db_path)
    state_dir = resolve_runtime_state_dir(runtime_dir, cfg_log_dir)
    os.makedirs(state_dir, exist_ok=True)
    _write_runtime_state_triplet(state_dir, host, port, db_for_runtime)

    mirror_log_dir = _runtime_log_mirror_dir(runtime_dir, cfg_log_dir)
    if mirror_log_dir:
        try:
            os.makedirs(mirror_log_dir, exist_ok=True)
            _write_runtime_state_triplet(mirror_log_dir, host, port, db_for_runtime)
        except Exception:
            pass
    if logger is not None:
        try:
            host_file, port_file, db_file, _contract_file = _state_contract_paths(state_dir)
            logger.info(f"端口已写入：{port_file} -> {int(port)}")
            logger.info(f"Host 已写入：{host_file}")
            logger.info(f"DB 路径已写入：{db_file} -> {db_for_runtime}")
        except Exception:
            pass


def default_chrome_profile_dir(runtime_dir: str) -> str:
    local_appdata = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local_appdata:
        return os.path.join(local_appdata, "APS", "Chrome109Profile")
    return os.path.join(str(runtime_dir), "chrome109_profile")


def _runtime_contract_path(state_dir: str) -> str:
    return os.path.join(str(state_dir), "aps_runtime.json")


def _runtime_contract_payload(
    runtime_dir: str,
    host: str,
    port: int,
    *,
    db_path: str | None,
    shutdown_token: str,
    ui_mode: str,
    log_dir: str | None,
    backup_dir: str | None,
    excel_template_dir: str | None,
    exe_path: str | None = None,
    chrome_profile_dir: str | None = None,
    owner: str | None = None,
) -> Dict[str, Any]:
    host_for_client = (str(host or "").strip() or "127.0.0.1")
    if host_for_client == "0.0.0.0":
        host_for_client = "127.0.0.1"
    runtime_dir_abs = os.path.abspath(str(runtime_dir))
    return {
        "contract_version": int(_RUNTIME_CONTRACT_VERSION),
        "pid": int(os.getpid()),
        "host": host_for_client,
        "port": int(port),
        "ui_mode": str(ui_mode or "").strip() or "unknown",
        "runtime_dir": runtime_dir_abs,
        "exe_path": os.path.abspath(str(exe_path or sys.executable or "")).strip(),
        "owner": str(owner or current_runtime_owner()).strip() or "unknown",
        "shutdown_path": _RUNTIME_SHUTDOWN_PATH,
        "shutdown_token": str(shutdown_token or "").strip(),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "db_path": _normalize_db_path_for_runtime(db_path),
        "chrome_profile_dir": os.path.abspath(
            str(chrome_profile_dir or default_chrome_profile_dir(runtime_dir_abs))
        ),
        "data_dirs": {
            "log_dir": os.path.abspath(str(log_dir or _runtime_log_dir(runtime_dir_abs))),
            "backup_dir": os.path.abspath(str(backup_dir or os.path.join(runtime_dir_abs, "backups"))),
            "excel_template_dir": os.path.abspath(
                str(excel_template_dir or os.path.join(runtime_dir_abs, "templates_excel"))
            ),
        },
    }


def write_runtime_contract_file(
    runtime_dir: str,
    host: str,
    port: int,
    *,
    db_path: str | None,
    shutdown_token: str,
    ui_mode: str,
    log_dir: str | None,
    backup_dir: str | None,
    excel_template_dir: str | None,
    exe_path: str | None = None,
    chrome_profile_dir: str | None = None,
    owner: str | None = None,
    logger: logging.Logger | None = None,
) -> str:
    payload = _runtime_contract_payload(
        runtime_dir,
        host,
        port,
        db_path=db_path,
        shutdown_token=shutdown_token,
        ui_mode=ui_mode,
        log_dir=log_dir,
        backup_dir=backup_dir,
        excel_template_dir=excel_template_dir,
        exe_path=exe_path,
        chrome_profile_dir=chrome_profile_dir,
        owner=owner,
    )
    state_dir = resolve_runtime_state_dir(runtime_dir, log_dir)
    os.makedirs(state_dir, exist_ok=True)
    contract_path = _runtime_contract_path(state_dir)
    with open(contract_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    mirror_log_dir = _runtime_log_mirror_dir(runtime_dir, log_dir)
    if mirror_log_dir:
        try:
            os.makedirs(mirror_log_dir, exist_ok=True)
            mirror_contract_path = _runtime_contract_path(mirror_log_dir)
            with open(mirror_contract_path, "w", encoding="utf-8") as f2:
                json.dump(payload, f2, ensure_ascii=False, indent=2, sort_keys=True)
                f2.write("\n")
        except Exception:
            pass
    if logger is not None:
        try:
            logger.info(f"运行时契约已写入：{contract_path}")
        except Exception:
            pass
    return contract_path


def read_runtime_contract(runtime_dir: str) -> Optional[Dict[str, Any]]:
    state_dir = _resolve_runtime_state_dir_for_read(runtime_dir)
    contract_path = _runtime_contract_path(state_dir)
    if not os.path.exists(contract_path):
        return None
    try:
        with open(contract_path, encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    try:
        payload["contract_version"] = int(payload.get("contract_version") or 0)
    except Exception:
        payload["contract_version"] = 0
    if payload["contract_version"] != _RUNTIME_CONTRACT_VERSION:
        return None
    try:
        payload["pid"] = int(payload.get("pid") or 0)
    except Exception:
        payload["pid"] = 0
    try:
        payload["port"] = int(payload.get("port") or 0)
    except Exception:
        payload["port"] = 0
    return payload


def delete_runtime_contract_files(runtime_dir: str) -> None:
    state_dir = _resolve_runtime_state_dir_for_read(runtime_dir)
    log_dirs = [state_dir]
    contract_path = _runtime_contract_path(state_dir)
    try:
        with open(contract_path, encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            runtime_dir_raw = str(payload.get("runtime_dir") or "").strip()
            if runtime_dir_raw:
                runtime_log_dir = os.path.abspath(_runtime_log_dir(runtime_dir_raw))
                if os.path.normcase(runtime_log_dir) != os.path.normcase(os.path.abspath(state_dir)):
                    log_dirs.append(runtime_log_dir)
            data_dirs = payload.get("data_dirs") or {}
            if isinstance(data_dirs, dict):
                mirror_log_dir = str(data_dirs.get("log_dir") or "").strip()
                if mirror_log_dir:
                    mirror_log_dir_abs = os.path.abspath(mirror_log_dir)
                    if os.path.normcase(mirror_log_dir_abs) != os.path.normcase(os.path.abspath(state_dir)):
                        log_dirs.append(mirror_log_dir_abs)
    except Exception:
        pass

    paths = []
    for log_dir in log_dirs:
        paths.extend(
            [
                os.path.join(log_dir, "aps_runtime.json"),
                os.path.join(log_dir, "aps_port.txt"),
                os.path.join(log_dir, "aps_host.txt"),
                os.path.join(log_dir, "aps_db_path.txt"),
                os.path.join(log_dir, _RUNTIME_LOCK_FILE),
                os.path.join(log_dir, _RUNTIME_ERROR_FILE),
            ]
        )
    for path in paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except Exception:
            pass


def _build_shutdown_url(contract: Dict[str, Any]) -> Optional[str]:
    host = str(contract.get("host") or "").strip() or "127.0.0.1"
    try:
        port = int(contract.get("port") or 0)
    except Exception:
        port = 0
    if port <= 0:
        return None
    shutdown_path = str(contract.get("shutdown_path") or _RUNTIME_SHUTDOWN_PATH).strip() or _RUNTIME_SHUTDOWN_PATH
    if not shutdown_path.startswith("/"):
        shutdown_path = "/" + shutdown_path
    return f"http://{host}:{port}{shutdown_path}"


def _request_runtime_shutdown(contract: Dict[str, Any], timeout_s: float = 3.0) -> bool:
    url = _build_shutdown_url(contract)
    token = str(contract.get("shutdown_token") or "").strip()
    if not url or not token:
        return False
    req = urllib.request.Request(url, method="POST", data=b"")
    req.add_header("X-APS-Shutdown-Token", token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=max(float(timeout_s), 0.5)) as resp:
            return int(getattr(resp, "status", 200)) < 400
    except urllib.error.HTTPError as e:
        return int(getattr(e, "code", 500)) < 400
    except Exception:
        return False


def _probe_runtime_health(host: str, port: int, timeout_s: float = 1.5) -> bool:
    url = f"http://{str(host or '').strip() or '127.0.0.1'}:{int(port)}/system/health"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=max(float(timeout_s), 0.2)) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return False
    return (
        payload.get("app") == "aps"
        and payload.get("status") == "ok"
        and int(payload.get("contract_version") or 0) == 1
    )


def _query_process_executable_path(pid: int) -> Optional[str]:
    try:
        pid_i = int(pid)
    except Exception:
        return None
    if pid_i <= 0:
        return None
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["wmic", "process", "where", f"processid={pid_i}", "get", "ExecutablePath", "/value"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except Exception:
            return None
        text = (result.stdout or "") + "\n" + (result.stderr or "")
        for line in text.splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip().lower() == "executablepath":
                value_s = value.strip()
                if value_s:
                    return os.path.normcase(os.path.abspath(value_s))
                return ""
        return ""
    return None


def _pid_matches_contract(pid: int, expected_exe_path: str) -> Optional[bool]:
    actual = _query_process_executable_path(pid)
    if actual is None:
        return None
    if actual == "":
        return False
    expected = os.path.normcase(os.path.abspath(str(expected_exe_path or "").strip()))
    if not expected:
        return None
    return actual == expected


def _kill_runtime_pid(pid: int) -> bool:
    try:
        pid_i = int(pid)
    except Exception:
        return False
    if pid_i <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid_i), "/F", "/T"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception:
            return False
        return int(result.returncode or 0) == 0
    return False


def _list_aps_chrome_pids(profile_dir: str) -> list[int]:
    marker = os.path.basename(str(profile_dir or "").rstrip("\\/")) or "Chrome109Profile"
    if os.name != "nt":
        return []
    try:
        result = subprocess.run(
            [
                "wmic",
                "process",
                "where",
                f"Name='chrome.exe' and CommandLine like '%{marker}%'",
                "get",
                "ProcessId",
                "/value",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception:
        return []
    pids: list[int] = []
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip().lower() == "processid":
            try:
                pid_i = int(str(value).strip())
            except Exception:
                continue
            if pid_i > 0 and pid_i not in pids:
                pids.append(pid_i)
    return pids


def stop_aps_chrome_processes(profile_dir: str | None, logger: logging.Logger | None = None) -> bool:
    target_profile = str(profile_dir or "").strip()
    if not target_profile:
        return True
    pids = _list_aps_chrome_pids(target_profile)
    ok = True
    for pid in pids:
        if not _kill_runtime_pid(pid):
            ok = False
            if logger is not None:
                try:
                    logger.warning(f"关闭 APS Chrome 进程失败：pid={pid}")
                except Exception:
                    pass
    return ok


def stop_runtime_from_dir(
    runtime_dir: str,
    *,
    stop_aps_chrome: bool = False,
    timeout_s: float = 15.0,
    logger: logging.Logger | None = None,
) -> int:
    runtime_dir_abs, state_dir = _resolve_runtime_stop_context(runtime_dir)
    contract = read_runtime_contract(state_dir)
    if contract is None:
        host_file = os.path.join(state_dir, "aps_host.txt")
        port_file = os.path.join(state_dir, "aps_port.txt")
        if os.path.exists(host_file) and os.path.exists(port_file):
            try:
                with open(host_file, encoding="utf-8") as f:
                    host0 = (f.read() or "").strip() or "127.0.0.1"
                with open(port_file, encoding="utf-8") as f:
                    port0 = int((f.read() or "").strip())
            except Exception:
                host0 = ""
                port0 = 0
            if host0 and port0 > 0 and _probe_runtime_health(host0, port0, timeout_s=1.0):
                return 1
        delete_runtime_contract_files(state_dir)
        if stop_aps_chrome:
            stop_aps_chrome_processes(default_chrome_profile_dir(runtime_dir_abs), logger=logger)
        return 0

    host = str(contract.get("host") or "").strip() or "127.0.0.1"
    try:
        port = int(contract.get("port") or 0)
    except Exception:
        port = 0
    pid = int(contract.get("pid") or 0)
    expected_exe_path = str(contract.get("exe_path") or "").strip()
    grace_deadline = time.time() + max(min(float(timeout_s), 12.0), 2.0)
    shutdown_requested = _request_runtime_shutdown(contract, timeout_s=3.0)

    while time.time() < grace_deadline:
        if port > 0 and not _probe_runtime_health(host, port, timeout_s=0.5):
            delete_runtime_contract_files(state_dir)
            if stop_aps_chrome:
                stop_aps_chrome_processes(contract.get("chrome_profile_dir"), logger=logger)
            return 0
        time.sleep(0.25)

    pid_match = _pid_matches_contract(pid, expected_exe_path)
    helper_exe_path = os.path.normcase(os.path.abspath(str(sys.executable or "").strip()))
    expected_exe_norm = os.path.normcase(os.path.abspath(expected_exe_path)) if expected_exe_path else ""
    can_kill_by_pid = pid_match is True or (pid_match is None and expected_exe_norm and expected_exe_norm == helper_exe_path)
    if pid > 0 and can_kill_by_pid:
        _ = _kill_runtime_pid(pid)
        kill_deadline = time.time() + 6.0
        while time.time() < kill_deadline:
            if port > 0 and not _probe_runtime_health(host, port, timeout_s=0.5):
                delete_runtime_contract_files(state_dir)
                if stop_aps_chrome:
                    stop_aps_chrome_processes(contract.get("chrome_profile_dir"), logger=logger)
                return 0
            time.sleep(0.25)

    if logger is not None:
        try:
            logger.warning(
                "运行时停止失败：shutdown_requested=%s pid=%s pid_match=%s host=%s port=%s",
                shutdown_requested,
                pid,
                pid_match,
                host,
                port,
            )
        except Exception:
            pass
    return 1


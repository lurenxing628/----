from __future__ import annotations

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


def write_runtime_host_port_files(
    runtime_dir: str,
    cfg_log_dir: str | None,
    host: str,
    port: int,
    db_path: str | None = None,
    *,
    logger: logging.Logger | None = None,
) -> None:
    runtime_log_dir = os.path.join(runtime_dir, "logs")
    os.makedirs(runtime_log_dir, exist_ok=True)
    port_file = os.path.join(runtime_log_dir, "aps_port.txt")
    host_file = os.path.join(runtime_log_dir, "aps_host.txt")
    db_file = os.path.join(runtime_log_dir, "aps_db_path.txt")

    with open(port_file, "w", encoding="utf-8") as f:
        f.write(str(int(port)) + "\n")

    host_for_client = (str(host or "").strip() or "127.0.0.1")
    if host_for_client == "0.0.0.0":
        host_for_client = "127.0.0.1"
    with open(host_file, "w", encoding="utf-8") as f:
        f.write(str(host_for_client) + "\n")

    db_for_runtime = _normalize_db_path_for_runtime(db_path)
    with open(db_file, "w", encoding="utf-8") as f:
        f.write(db_for_runtime + "\n")

    cfg_log_dir_s = ""
    try:
        cfg_log_dir_s = str(cfg_log_dir).strip() if cfg_log_dir is not None else ""
    except Exception:
        cfg_log_dir_s = ""
    if cfg_log_dir_s:
        try:
            if os.path.abspath(cfg_log_dir_s) != os.path.abspath(runtime_log_dir):
                os.makedirs(cfg_log_dir_s, exist_ok=True)
                mirror_port_file = os.path.join(cfg_log_dir_s, "aps_port.txt")
                with open(mirror_port_file, "w", encoding="utf-8") as f2:
                    f2.write(str(int(port)) + "\n")
                mirror_host_file = os.path.join(cfg_log_dir_s, "aps_host.txt")
                with open(mirror_host_file, "w", encoding="utf-8") as f3:
                    f3.write(str(host_for_client) + "\n")
                mirror_db_file = os.path.join(cfg_log_dir_s, "aps_db_path.txt")
                with open(mirror_db_file, "w", encoding="utf-8") as f4:
                    f4.write(db_for_runtime + "\n")
        except Exception:
            pass
    if logger is not None:
        try:
            logger.info(f"端口已写入：{port_file} -> {int(port)}")
            logger.info(f"Host 已写入：{host_file} -> {host_for_client}")
            logger.info(f"DB 路径已写入：{db_file} -> {db_for_runtime}")
        except Exception:
            pass


def default_chrome_profile_dir(runtime_dir: str) -> str:
    local_appdata = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local_appdata:
        return os.path.join(local_appdata, "APS", "Chrome109Profile")
    return os.path.join(str(runtime_dir), "chrome109_profile")


def _runtime_log_dir(runtime_dir: str) -> str:
    return os.path.join(str(runtime_dir), "logs")


def _runtime_contract_path(runtime_dir: str) -> str:
    return os.path.join(_runtime_log_dir(runtime_dir), "aps_runtime.json")


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
    )
    log_dir_abs = _runtime_log_dir(runtime_dir)
    os.makedirs(log_dir_abs, exist_ok=True)
    contract_path = _runtime_contract_path(runtime_dir)
    with open(contract_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    if logger is not None:
        try:
            logger.info(f"运行时契约已写入：{contract_path}")
        except Exception:
            pass
    return contract_path


def read_runtime_contract(runtime_dir: str) -> Optional[Dict[str, Any]]:
    contract_path = _runtime_contract_path(runtime_dir)
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
    runtime_dir_abs = os.path.abspath(str(runtime_dir))
    runtime_log_dir = _runtime_log_dir(runtime_dir_abs)
    contract_path = _runtime_contract_path(runtime_dir_abs)
    log_dirs = [runtime_log_dir]
    try:
        with open(contract_path, encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            data_dirs = payload.get("data_dirs") or {}
            if isinstance(data_dirs, dict):
                mirror_log_dir = str(data_dirs.get("log_dir") or "").strip()
                if mirror_log_dir:
                    mirror_log_dir_abs = os.path.abspath(mirror_log_dir)
                    if os.path.normcase(mirror_log_dir_abs) != os.path.normcase(os.path.abspath(runtime_log_dir)):
                        log_dirs.append(mirror_log_dir_abs)
    except Exception:
        pass

    paths = [contract_path]
    for log_dir in log_dirs:
        paths.extend(
            [
                os.path.join(log_dir, "aps_port.txt"),
                os.path.join(log_dir, "aps_host.txt"),
                os.path.join(log_dir, "aps_db_path.txt"),
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
    runtime_dir_abs = os.path.abspath(str(runtime_dir))
    contract = read_runtime_contract(runtime_dir_abs)
    if contract is None:
        host_file = os.path.join(_runtime_log_dir(runtime_dir_abs), "aps_host.txt")
        port_file = os.path.join(_runtime_log_dir(runtime_dir_abs), "aps_port.txt")
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
        delete_runtime_contract_files(runtime_dir_abs)
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
            delete_runtime_contract_files(runtime_dir_abs)
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
                delete_runtime_contract_files(runtime_dir_abs)
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


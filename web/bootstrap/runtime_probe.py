from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple

_EXPECTED_CONTRACT_VERSION = 1


def _runtime_log_paths(runtime_dir: str) -> Tuple[str, str]:
    log_dir = os.path.join(str(runtime_dir), "logs")
    return (
        os.path.join(log_dir, "aps_host.txt"),
        os.path.join(log_dir, "aps_port.txt"),
    )


def _runtime_db_path_file(runtime_dir: str) -> str:
    log_dir = os.path.join(str(runtime_dir), "logs")
    return os.path.join(log_dir, "aps_db_path.txt")


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read().strip()


def _normalize_db_path(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    return os.path.normcase(os.path.abspath(raw))


def build_base_url(host: str, port: int) -> str:
    host_s = str(host or "").strip() or "127.0.0.1"
    if host_s == "0.0.0.0":
        host_s = "127.0.0.1"
    return f"http://{host_s}:{int(port)}"


def read_runtime_host_port(runtime_dir: str) -> Optional[Tuple[str, int]]:
    host_file, port_file = _runtime_log_paths(runtime_dir)
    if not os.path.exists(host_file) or not os.path.exists(port_file):
        return None
    try:
        host = _read_text(host_file) or "127.0.0.1"
        port = int(_read_text(port_file))
    except Exception:
        return None
    if port <= 0:
        return None
    return (host, port)


def read_runtime_db_path(runtime_dir: str) -> Optional[str]:
    db_file = _runtime_db_path_file(runtime_dir)
    if not os.path.exists(db_file):
        return None
    try:
        db_path = _normalize_db_path(_read_text(db_file))
    except Exception:
        return None
    if not db_path:
        return None
    return db_path


def delete_stale_runtime_files(runtime_dir: str) -> None:
    host_file, port_file = _runtime_log_paths(runtime_dir)
    db_file = _runtime_db_path_file(runtime_dir)
    for path in (host_file, port_file, db_file):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except Exception:
            pass


def probe_health(base_url: str, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
    url = str(base_url).rstrip("/") + "/system/health"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return None
    try:
        contract_version = int(payload.get("contract_version") or 0)
    except Exception:
        contract_version = 0
    if (
        payload.get("app") != "aps"
        or payload.get("status") != "ok"
        or contract_version != _EXPECTED_CONTRACT_VERSION
    ):
        return None
    return payload


def _build_endpoint_result(host: str, port: int, source: str, health: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "host": str(host),
        "port": int(port),
        "base_url": build_base_url(host, port),
        "source": str(source),
        "health": dict(health),
    }


def resolve_healthy_endpoint(
    runtime_dir: str,
    preferred_host: str | None = None,
    preferred_port: int | None = None,
    timeout: float = 2.0,
) -> Optional[Dict[str, Any]]:
    if preferred_host is not None and preferred_port is not None:
        try:
            host = str(preferred_host).strip() or "127.0.0.1"
            port = int(preferred_port)
        except Exception:
            host = ""
            port = 0
        if host and port > 0:
            health = probe_health(build_base_url(host, port), timeout=timeout)
            if health is not None:
                return _build_endpoint_result(host, port, "preferred", health)

    runtime = read_runtime_host_port(runtime_dir)
    if runtime is None:
        return None
    host, port = runtime
    health = probe_health(build_base_url(host, port), timeout=timeout)
    if health is None:
        return None
    return _build_endpoint_result(host, port, "runtime_files", health)


def wait_for_healthy_runtime_endpoint(
    runtime_dir: str,
    timeout_s: int,
    interval_s: float = 0.5,
) -> Dict[str, Any]:
    deadline = time.time() + max(int(timeout_s), 1)
    last_seen: Optional[str] = None
    sleep_s = max(float(interval_s), 0.05)
    while time.time() < deadline:
        runtime = read_runtime_host_port(runtime_dir)
        if runtime is not None:
            host, port = runtime
            last_seen = f"{host}:{port}"
            health = probe_health(build_base_url(host, port), timeout=2.0)
            if health is not None:
                return _build_endpoint_result(host, port, "runtime_files", health)
        time.sleep(sleep_s)
    if last_seen is not None:
        raise TimeoutError(f"Timed out waiting for healthy runtime endpoint: {last_seen}")
    raise TimeoutError(f"Timed out waiting for runtime host/port files in {os.path.join(str(runtime_dir), 'logs')}")

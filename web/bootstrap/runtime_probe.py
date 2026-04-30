from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .launcher_observability import launcher_log_warning
from .runtime_capabilities import CapabilityResult, available, degraded

_EXPECTED_CONTRACT_VERSION = 1


@dataclass(frozen=True)
class ProbeHealthResult:
    ok: bool
    base_url: str
    reason: str = ""
    status: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None
    error: str = ""

    def to_capability(self) -> CapabilityResult:
        details = {"base_url": self.base_url}
        if self.status is not None:
            details["status"] = str(self.status)
        if self.ok:
            return available("runtime-health", details)
        if self.error:
            details["error"] = self.error
        return degraded("runtime-health", self.reason or "runtime_health_failed", details)


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
    except Exception as exc:
        launcher_log_warning(None, "读取运行时 host/port 文件失败，已按无运行实例处理：dir=%s error=%s", runtime_dir, exc, runtime_dir=runtime_dir)
        return None
    if port <= 0:
        launcher_log_warning(None, "运行时端口文件非法，已按无运行实例处理：dir=%s port=%s", runtime_dir, port, runtime_dir=runtime_dir)
        return None
    return (host, port)


def read_runtime_db_path(runtime_dir: str) -> Optional[str]:
    db_file = _runtime_db_path_file(runtime_dir)
    if not os.path.exists(db_file):
        return None
    try:
        db_path = _normalize_db_path(_read_text(db_file))
    except Exception as exc:
        launcher_log_warning(None, "读取运行时 db_path 文件失败，已按无 db_path 处理：path=%s error=%s", db_file, exc, runtime_dir=runtime_dir)
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
        except Exception as exc:
            launcher_log_warning(None, "删除运行时残留文件失败，已继续：path=%s error=%s", path, exc, runtime_dir=runtime_dir)


def probe_health_result(
    base_url: str,
    timeout: float = 2.0,
    *,
    log_failures: bool = False,
    runtime_dir: Optional[str] = None,
) -> ProbeHealthResult:
    base_url_s = str(base_url).rstrip("/")
    url = str(base_url).rstrip("/") + "/system/health"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200))
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception as exc:
        if log_failures:
            launcher_log_warning(None, "运行时健康探测失败：url=%s error=%s", url, exc, runtime_dir=runtime_dir)
        return ProbeHealthResult(False, base_url_s, "request_failed", error=str(exc))
    try:
        contract_version = int(payload.get("contract_version") or 0)
    except Exception as exc:
        if log_failures:
            launcher_log_warning(None, "运行时健康响应版本非法：url=%s error=%s", url, exc, runtime_dir=runtime_dir)
        return ProbeHealthResult(False, base_url_s, "invalid_contract_version", status=status, payload=payload, error=str(exc))
    if (
        payload.get("app") != "aps"
        or payload.get("status") != "ok"
        or contract_version != _EXPECTED_CONTRACT_VERSION
    ):
        return ProbeHealthResult(False, base_url_s, "unexpected_health_payload", status=status, payload=payload)
    return ProbeHealthResult(True, base_url_s, status=status, payload=payload)


def probe_health(base_url: str, timeout: float = 2.0, *, log_failures: bool = False) -> Optional[Dict[str, Any]]:
    result = probe_health_result(base_url, timeout=timeout, log_failures=log_failures)
    return result.payload if result.ok else None


_DEFAULT_PROBE_HEALTH = probe_health


def _probe_health_for_resolve(base_url: str, timeout: float, runtime_dir: str) -> ProbeHealthResult:
    if probe_health is not _DEFAULT_PROBE_HEALTH:
        payload = probe_health(base_url, timeout=timeout, log_failures=True)
        return ProbeHealthResult(bool(payload), base_url, "" if payload else "legacy_probe_failed", payload=payload)
    return probe_health_result(base_url, timeout=timeout, log_failures=True, runtime_dir=runtime_dir)


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
    preferred_host: Optional[str] = None,
    preferred_port: Optional[int] = None,
    timeout: float = 2.0,
) -> Optional[Dict[str, Any]]:
    if preferred_host is not None and preferred_port is not None:
        try:
            host = str(preferred_host).strip() or "127.0.0.1"
            port = int(preferred_port)
        except Exception as exc:
            launcher_log_warning(
                None,
                "preferred 端点参数非法，已跳过 preferred 探测：host=%r port=%r error=%s",
                preferred_host,
                preferred_port,
                exc,
                runtime_dir=runtime_dir,
            )
            host = ""
            port = 0
        if host and port > 0:
            health_result = _probe_health_for_resolve(build_base_url(host, port), timeout, runtime_dir)
            health_result.to_capability()
            if health_result.payload is not None and health_result.ok:
                return _build_endpoint_result(host, port, "preferred", health_result.payload)
            launcher_log_warning(
                None,
                "preferred 端点健康探测未通过：host=%s port=%s reason=%s error=%s",
                host,
                port,
                health_result.reason,
                health_result.error,
                runtime_dir=runtime_dir,
            )

    runtime = read_runtime_host_port(runtime_dir)
    if runtime is None:
        return None
    host, port = runtime
    health_result = _probe_health_for_resolve(build_base_url(host, port), timeout, runtime_dir)
    health_result.to_capability()
    if health_result.payload is None or not health_result.ok:
        launcher_log_warning(
            None,
            "运行时文件端点健康探测未通过：host=%s port=%s reason=%s error=%s",
            host,
            port,
            health_result.reason,
            health_result.error,
            runtime_dir=runtime_dir,
        )
        return None
    return _build_endpoint_result(host, port, "runtime_files", health_result.payload)


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

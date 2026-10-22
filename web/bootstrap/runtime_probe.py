from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from core.infrastructure.safe_files import read_fixed_text

from .launcher_observability import launcher_log_warning

_EXPECTED_CONTRACT_VERSION = 1


@dataclass(frozen=True)
class ProbeHealthResult:
    ok: bool
    base_url: str
    reason: str = ""
    status: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None
    error: str = ""

def _runtime_log_paths(runtime_dir: str) -> Tuple[str, str]:
    log_dir = os.path.join(str(runtime_dir), "logs")
    return (
        os.path.join(log_dir, "aps_host.txt"),
        os.path.join(log_dir, "aps_port.txt"),
    )


def _read_text(path: str) -> str:
    return read_fixed_text(path).strip()


def _read_optional_text(path: str) -> Optional[str]:
    try:
        return _read_text(path)
    except FileNotFoundError:
        return None


def build_base_url(host: str, port: int) -> str:
    host_s = str(host or "").strip() or "127.0.0.1"
    if host_s == "0.0.0.0":
        host_s = "127.0.0.1"
    return f"http://{host_s}:{int(port)}"


def read_runtime_host_port(runtime_dir: str) -> Optional[Tuple[str, int]]:
    host_file, port_file = _runtime_log_paths(runtime_dir)
    try:
        host_raw = _read_optional_text(host_file)
        port_raw = _read_optional_text(port_file)
        if host_raw is None or port_raw is None:
            return None
        host = host_raw or "127.0.0.1"
        port = int(port_raw)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        launcher_log_warning(None, "读取运行时 host/port 文件失败，已按无运行实例处理：dir=%s error=%s", runtime_dir, exc, runtime_dir=runtime_dir)
        return None
    if port <= 0:
        launcher_log_warning(None, "运行时端口文件非法，已按无运行实例处理：dir=%s port=%s", runtime_dir, port, runtime_dir=runtime_dir)
        return None
    return (host, port)


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
            payload = json.loads(resp.read().decode("utf-8"))
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
            health_result = probe_health_result(build_base_url(host, port), timeout=timeout, log_failures=True, runtime_dir=runtime_dir)
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
    health_result = probe_health_result(build_base_url(host, port), timeout=timeout, log_failures=True, runtime_dir=runtime_dir)
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

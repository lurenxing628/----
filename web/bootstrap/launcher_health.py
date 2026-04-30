from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .launcher_observability import launcher_log_warning
from .runtime_capabilities import CapabilityResult, available, degraded


@dataclass(frozen=True)
class HealthProbeResult:
    ok: bool
    url: str
    reason: str = ""
    status: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None
    error: str = ""

    def to_capability(self) -> CapabilityResult:
        details = {"url": self.url}
        if self.status is not None:
            details["status"] = str(self.status)
        if self.ok:
            return available("runtime-health", details)
        if self.error:
            details["error"] = self.error
        return degraded("runtime-health", self.reason or "runtime_health_failed", details)


def probe_runtime_health_result(
    host: str,
    port: int,
    timeout_s: float = 1.5,
    *,
    log_failures: bool = False,
    state_dir: Optional[str] = None,
) -> HealthProbeResult:
    host_s = str(host or "").strip() or "127.0.0.1"
    try:
        port_i = int(port)
    except (TypeError, ValueError) as exc:
        url = f"http://{host_s}:0/system/health"
        if log_failures:
            launcher_log_warning(None, "运行时健康探测端口非法：host=%s port=%r error=%s", host_s, port, exc, state_dir=state_dir)
        return HealthProbeResult(False, url, "invalid_port", error=str(exc))
    url = f"http://{host_s}:{port_i}/system/health"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=max(float(timeout_s), 0.2)) as resp:
            status = int(getattr(resp, "status", 200))
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except (OSError, TypeError, ValueError) as exc:
        if log_failures:
            launcher_log_warning(None, "运行时健康探测失败：url=%s error=%s", url, exc, state_dir=state_dir)
        return HealthProbeResult(False, url, "request_failed", error=str(exc))
    try:
        contract_version = int(payload.get("contract_version") or 0)
    except (AttributeError, TypeError, ValueError) as exc:
        if log_failures:
            launcher_log_warning(None, "运行时健康响应版本非法：url=%s error=%s", url, exc, state_dir=state_dir)
        return HealthProbeResult(False, url, "invalid_contract_version", status=status, payload=payload, error=str(exc))
    ok = payload.get("app") == "aps" and payload.get("status") == "ok" and contract_version == 1
    reason = "" if ok else "unexpected_health_payload"
    if not ok and log_failures:
        launcher_log_warning(None, "运行时健康响应不匹配：url=%s payload=%s", url, payload, state_dir=state_dir)
    return HealthProbeResult(ok, url, reason, status=status, payload=payload)

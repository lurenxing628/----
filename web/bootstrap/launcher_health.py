from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .launcher_observability import launcher_log_warning


@dataclass(frozen=True)
class HealthProbeResult:
    ok: bool
    url: str
    reason: str = ""
    status: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None
    error: str = ""


def probe_runtime_health_result(base_url: str, timeout_s: float, *, log_failures: bool = False) -> HealthProbeResult:
    url = base_url.rstrip("/") + "/system/health"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = resp.status
            payload = json.loads(resp.read().decode("utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        if log_failures:
            launcher_log_warning(None, "运行时健康探测失败：url=%s error=%s", url, exc)
        return HealthProbeResult(False, url, "request_failed", error=str(exc))
    if not isinstance(payload, dict):
        error = f"expected object, got {type(payload).__name__}"
        if log_failures:
            launcher_log_warning(None, "运行时健康响应版本非法：url=%s error=%s", url, error)
        return HealthProbeResult(False, url, "invalid_contract_version", status=status, payload=None, error=error)
    contract_version = payload.get("contract_version")
    if type(contract_version) is not int:
        error = f"expected int, got {type(contract_version).__name__}"
        if log_failures:
            launcher_log_warning(None, "运行时健康响应版本非法：url=%s error=%s", url, error)
        return HealthProbeResult(False, url, "invalid_contract_version", status=status, payload=payload, error=error)
    ok = payload.get("app") == "aps" and payload.get("status") == "ok" and contract_version == 1
    reason = "" if ok else "unexpected_health_payload"
    if not ok and log_failures:
        launcher_log_warning(None, "运行时健康响应不匹配：url=%s payload=%s", url, payload)
    return HealthProbeResult(ok, url, reason, status=status, payload=payload)

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .launcher_observability import launcher_log_warning
from .runtime_capabilities import CapabilityResult, available, degraded


@dataclass(frozen=True)
class BindProbeResult:
    ok: bool
    host: str
    port: int
    reason: str = ""
    error: str = ""

    def to_capability(self) -> CapabilityResult:
        details = {"host": self.host, "port": str(self.port)}
        if self.ok:
            return available("bind-probe", details)
        if self.error:
            details["error"] = self.error
        return degraded("bind-probe", self.reason or "bind_failed", details)


def pick_bind_host(raw_host: Optional[str], *, logger: Optional[logging.Logger] = None) -> str:
    host = (raw_host or "").strip() or "127.0.0.1"
    try:
        ip = ipaddress.ip_address(host)
        if getattr(ip, "version", None) != 4:
            raise ValueError("not ipv4")
    except ValueError as exc:
        launcher_log_warning(logger, "APS_HOST 非法或非 IPv4：%s，已回退到 127.0.0.1：%s", host, exc)
        host = "127.0.0.1"
    return host


def _can_bind_result(
    host0: str,
    port0: int,
    *,
    logger: Optional[logging.Logger] = None,
    log_failures: bool = False,
    state_dir: Optional[str] = None,
    runtime_dir: Optional[str] = None,
    cfg_log_dir: Optional[str] = None,
) -> BindProbeResult:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host_s = str(host0 or "").strip() or "127.0.0.1"
    try:
        port_i = int(port0)
    except Exception as exc:
        if log_failures:
            launcher_log_warning(
                logger,
                "端口绑定探测端口非法：host=%s port=%r error=%s",
                host_s,
                port0,
                exc,
                state_dir=state_dir,
                runtime_dir=runtime_dir,
                cfg_log_dir=cfg_log_dir,
            )
        return BindProbeResult(False, host_s, 0, "invalid_port", str(exc))
    try:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception as exc:
            if log_failures:
                launcher_log_warning(
                    logger,
                    "设置 socket 复用选项失败，继续尝试绑定：host=%s port=%s error=%s",
                    host_s,
                    port_i,
                    exc,
                    state_dir=state_dir,
                    runtime_dir=runtime_dir,
                    cfg_log_dir=cfg_log_dir,
                )
        s.bind((host_s, port_i))
        return BindProbeResult(True, host_s, port_i)
    except Exception as exc:
        if log_failures:
            launcher_log_warning(
                logger,
                "端口绑定探测失败：host=%s port=%s error=%s",
                host_s,
                port_i,
                exc,
                state_dir=state_dir,
                runtime_dir=runtime_dir,
                cfg_log_dir=cfg_log_dir,
            )
        return BindProbeResult(False, host_s, port_i, "bind_failed", str(exc))
    finally:
        try:
            s.close()
        except Exception as exc:
            launcher_log_warning(
                logger,
                "关闭端口探测 socket 失败，已继续：host=%s port=%s error=%s",
                host_s,
                port_i,
                exc,
                state_dir=state_dir,
                runtime_dir=runtime_dir,
                cfg_log_dir=cfg_log_dir,
            )


def _can_bind(
    host0: str,
    port0: int,
    *,
    logger: Optional[logging.Logger] = None,
    log_failures: bool = False,
) -> bool:
    return _can_bind_result(host0, port0, logger=logger, log_failures=log_failures).ok


_DEFAULT_CAN_BIND = _can_bind


def _candidate_ports(preferred: int) -> List[int]:
    candidates: List[int] = []
    for p in [preferred, 5000, 5705, 5706, 5707, 5710, 5711, 5712, 5713, 5714, 5715]:
        try:
            p0 = int(p)
        except (TypeError, ValueError):
            continue
        if p0 > 0 and p0 not in candidates:
            candidates.append(p0)
    return candidates


def _bind_ephemeral_port(
    host: str,
    fallback_host: str,
    *,
    logger: Optional[logging.Logger] = None,
    state_dir: Optional[str] = None,
    runtime_dir: Optional[str] = None,
    cfg_log_dir: Optional[str] = None,
) -> Tuple[str, int]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        try:
            s.bind((host, 0))
            _h, p = s.getsockname()
            return (host, int(p))
        except Exception as exc:
            launcher_log_warning(
                logger,
                "临时端口绑定失败，尝试回退 host：host=%s fallback_host=%s error=%s",
                host,
                fallback_host,
                exc,
                state_dir=state_dir,
                runtime_dir=runtime_dir,
                cfg_log_dir=cfg_log_dir,
            )
            s.close()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind((fallback_host, 0))
            _h, p = s.getsockname()
            return (fallback_host, int(p))
    finally:
        try:
            s.close()
        except Exception as exc:
            launcher_log_warning(
                logger,
                "关闭临时端口 socket 失败，已继续：%s",
                exc,
                state_dir=state_dir,
                runtime_dir=runtime_dir,
                cfg_log_dir=cfg_log_dir,
            )


def _bind_probe_for_pick(
    host: str,
    port: int,
    *,
    logger: Optional[logging.Logger] = None,
    state_dir: Optional[str] = None,
    runtime_dir: Optional[str] = None,
    cfg_log_dir: Optional[str] = None,
) -> BindProbeResult:
    if _can_bind is not _DEFAULT_CAN_BIND:
        ok = bool(_can_bind(host, port))
        return BindProbeResult(ok, str(host or "").strip() or "127.0.0.1", int(port or 0), "" if ok else "legacy_can_bind_false")
    return _can_bind_result(host, port, logger=logger, state_dir=state_dir, runtime_dir=runtime_dir, cfg_log_dir=cfg_log_dir)


def pick_port(
    host: str,
    preferred: int,
    *,
    logger: Optional[logging.Logger] = None,
    state_dir: Optional[str] = None,
    runtime_dir: Optional[str] = None,
    cfg_log_dir: Optional[str] = None,
) -> Tuple[str, int]:
    candidates = _candidate_ports(preferred)
    fallback_host = "127.0.0.1"
    last_result = BindProbeResult(False, str(host or "").strip() or fallback_host, 0, "no_candidates")
    for p in candidates:
        last_result = _bind_probe_for_pick(host, p, logger=logger, state_dir=state_dir, runtime_dir=runtime_dir, cfg_log_dir=cfg_log_dir)
        if last_result.ok:
            return (host, int(p))

    launcher_log_warning(
        logger,
        "候选端口在请求 host 上均不可用，将尝试回退 host：requested_host=%s candidates=%s last_reason=%s last_error=%s",
        host,
        candidates,
        last_result.reason,
        last_result.error,
        state_dir=state_dir,
        runtime_dir=runtime_dir,
        cfg_log_dir=cfg_log_dir,
    )

    if host != fallback_host:
        for p in candidates:
            last_result = _bind_probe_for_pick(
                fallback_host,
                p,
                logger=logger,
                state_dir=state_dir,
                runtime_dir=runtime_dir,
                cfg_log_dir=cfg_log_dir,
            )
            if last_result.ok:
                launcher_log_warning(
                    logger,
                    "已回退到本机监听地址：requested_host=%s fallback_host=%s fallback_port=%s last_reason=%s",
                    host,
                    fallback_host,
                    int(p),
                    last_result.reason,
                    state_dir=state_dir,
                    runtime_dir=runtime_dir,
                    cfg_log_dir=cfg_log_dir,
                )
                return (fallback_host, int(p))

    launcher_log_warning(
        logger,
        "固定候选端口均不可用，将绑定临时端口：requested_host=%s requested_port=%s fallback_host=%s last_reason=%s last_error=%s",
        host,
        preferred,
        fallback_host,
        last_result.reason,
        last_result.error,
        state_dir=state_dir,
        runtime_dir=runtime_dir,
        cfg_log_dir=cfg_log_dir,
    )
    return _bind_ephemeral_port(
        host,
        fallback_host,
        logger=logger,
        state_dir=state_dir,
        runtime_dir=runtime_dir,
        cfg_log_dir=cfg_log_dir,
    )

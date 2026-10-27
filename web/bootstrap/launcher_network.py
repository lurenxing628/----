from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .launcher_observability import launcher_log_warning


@dataclass(frozen=True)
class BindProbeResult:
    ok: bool
    host: str
    port: int
    reason: str = ""
    error: str = ""


def pick_bind_host(raw_host: Optional[str], *, logger: logging.Logger) -> str:
    host = (raw_host or "").strip() or "127.0.0.1"
    try:
        ip = ipaddress.ip_address(host)
        if ip.version != 4:
            raise ValueError("not ipv4")
    except ValueError as exc:
        launcher_log_warning(logger, "APS_HOST 非法或非 IPv4：%s，已回退到 127.0.0.1：%s", host, exc)
        host = "127.0.0.1"
    return host


def _can_bind_result(
    host: str,
    port: int,
    *,
    logger: logging.Logger,
    state_dir: str,
    runtime_dir: str,
) -> BindProbeResult:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        return BindProbeResult(True, host, port)
    except Exception as exc:
        return BindProbeResult(False, host, port, "bind_failed", str(exc))
    finally:
        try:
            s.close()
        except Exception as exc:
            launcher_log_warning(
                logger,
                "关闭端口探测 socket 失败，已继续：host=%s port=%s error=%s",
                host,
                port,
                exc,
                state_dir=state_dir,
                runtime_dir=runtime_dir,
            )


def candidate_ports(preferred: int) -> List[int]:
    candidates: List[int] = []
    for p in [preferred, 5000, 5705, 5706, 5707, 5710, 5711, 5712, 5713, 5714, 5715]:
        if p > 0 and p not in candidates:
            candidates.append(p)
    return candidates


def _bind_ephemeral_port(
    host: str,
    fallback_host: str,
    *,
    logger: logging.Logger,
    state_dir: str,
    runtime_dir: str,
) -> Tuple[str, int]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        try:
            s.bind((host, 0))
            _h, p = s.getsockname()
            return (host, p)
        except Exception as exc:
            launcher_log_warning(
                logger,
                "临时端口绑定失败，尝试回退 host：host=%s fallback_host=%s error=%s",
                host,
                fallback_host,
                exc,
                state_dir=state_dir,
                runtime_dir=runtime_dir,
            )
            s.close()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind((fallback_host, 0))
            _h, p = s.getsockname()
            return (fallback_host, p)
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
            )


def pick_port(
    host: str,
    preferred: int,
    *,
    logger: logging.Logger,
    state_dir: str,
    runtime_dir: str,
) -> Tuple[str, int]:
    candidates = candidate_ports(preferred)
    fallback_host = "127.0.0.1"
    last_result = BindProbeResult(False, host, 0, "no_candidates")
    for p in candidates:
        last_result = _can_bind_result(host, p, logger=logger, state_dir=state_dir, runtime_dir=runtime_dir)
        if last_result.ok:
            return (host, p)

    launcher_log_warning(
        logger,
        "候选端口在请求 host 上均不可用，将尝试回退 host：requested_host=%s candidates=%s last_reason=%s last_error=%s",
        host,
        candidates,
        last_result.reason,
        last_result.error,
        state_dir=state_dir,
        runtime_dir=runtime_dir,
    )

    if host != fallback_host:
        for p in candidates:
            last_result = _can_bind_result(
                fallback_host,
                p,
                logger=logger,
                state_dir=state_dir,
                runtime_dir=runtime_dir,
            )
            if last_result.ok:
                launcher_log_warning(
                    logger,
                    "已回退到本机监听地址：requested_host=%s fallback_host=%s fallback_port=%s last_reason=%s",
                    host,
                    fallback_host,
                    p,
                    last_result.reason,
                    state_dir=state_dir,
                    runtime_dir=runtime_dir,
                )
                return (fallback_host, p)

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
    )
    return _bind_ephemeral_port(
        host,
        fallback_host,
        logger=logger,
        state_dir=state_dir,
        runtime_dir=runtime_dir,
    )

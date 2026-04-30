from __future__ import annotations

import ipaddress
import logging
import socket

from core.infrastructure.logging import safe_log


def pick_bind_host(raw_host: str | None, *, logger: logging.Logger | None = None) -> str:
    host = (raw_host or "").strip() or "127.0.0.1"
    try:
        ip = ipaddress.ip_address(host)
        if getattr(ip, "version", None) != 4:
            raise ValueError("not ipv4")
    except ValueError as exc:
        safe_log(logger, "warning", "APS_HOST 非法或非 IPv4：%s，已回退到 127.0.0.1：%s", host, exc)
        host = "127.0.0.1"
    return host


def _can_bind(
    host0: str,
    port0: int,
    *,
    logger: logging.Logger | None = None,
    log_failures: bool = False,
) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception as exc:
            if log_failures:
                safe_log(logger, "warning", "设置 socket 复用选项失败，继续尝试绑定：host=%s port=%s error=%s", host0, port0, exc)
        s.bind((host0, int(port0)))
        return True
    except Exception as exc:
        if log_failures:
            safe_log(logger, "warning", "端口绑定探测失败：host=%s port=%s error=%s", host0, port0, exc)
        return False
    finally:
        try:
            s.close()
        except Exception as exc:
            safe_log(logger, "warning", "关闭端口探测 socket 失败，已继续：host=%s port=%s error=%s", host0, port0, exc)


def _candidate_ports(preferred: int) -> list[int]:
    candidates: list[int] = []
    for p in [preferred, 5000, 5705, 5706, 5707, 5710, 5711, 5712, 5713, 5714, 5715]:
        try:
            p0 = int(p)
        except (TypeError, ValueError):
            continue
        if p0 > 0 and p0 not in candidates:
            candidates.append(p0)
    return candidates


def _bind_ephemeral_port(host: str, fallback_host: str, *, logger: logging.Logger | None = None) -> tuple[str, int]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        try:
            s.bind((host, 0))
            _h, p = s.getsockname()
            return (host, int(p))
        except Exception as exc:
            safe_log(logger, "warning", "临时端口绑定失败，尝试回退 host：host=%s fallback_host=%s error=%s", host, fallback_host, exc)
            s.close()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind((fallback_host, 0))
            _h, p = s.getsockname()
            return (fallback_host, int(p))
    finally:
        try:
            s.close()
        except Exception as exc:
            safe_log(logger, "warning", "关闭临时端口 socket 失败，已继续：%s", exc)


def pick_port(host: str, preferred: int, *, logger: logging.Logger | None = None) -> tuple[str, int]:
    candidates = _candidate_ports(preferred)
    fallback_host = "127.0.0.1"
    for p in candidates:
        if _can_bind(host, p):
            return (host, int(p))

    safe_log(logger, "warning", "候选端口在请求 host 上均不可用，将尝试回退 host：host=%s candidates=%s", host, candidates)

    if host != fallback_host:
        for p in candidates:
            if _can_bind(fallback_host, p):
                safe_log(logger, "warning", "已回退到本机监听地址：host=%s port=%s", fallback_host, int(p))
                return (fallback_host, int(p))

    safe_log(logger, "warning", "固定候选端口均不可用，将绑定临时端口：host=%s fallback_host=%s", host, fallback_host)
    return _bind_ephemeral_port(host, fallback_host, logger=logger)

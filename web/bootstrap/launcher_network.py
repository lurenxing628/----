from __future__ import annotations

import ipaddress
import logging
import socket


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


def _candidate_ports(preferred: int) -> list[int]:
    candidates: list[int] = []
    for p in [preferred, 5000, 5705, 5706, 5707, 5710, 5711, 5712, 5713, 5714, 5715]:
        try:
            p0 = int(p)
        except Exception:
            continue
        if p0 > 0 and p0 not in candidates:
            candidates.append(p0)
    return candidates


def _bind_ephemeral_port(host: str, fallback_host: str) -> tuple[str, int]:
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


def pick_port(host: str, preferred: int, *, logger: logging.Logger | None = None) -> tuple[str, int]:
    candidates = _candidate_ports(preferred)
    fallback_host = "127.0.0.1"
    for p in candidates:
        if _can_bind(host, p):
            return (host, int(p))

    if host != fallback_host:
        for p in candidates:
            if _can_bind(fallback_host, p):
                return (fallback_host, int(p))

    return _bind_ephemeral_port(host, fallback_host)

from __future__ import annotations

import ipaddress
import logging
from typing import List, Optional

from .launcher_observability import launcher_log_warning


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


def candidate_ports(preferred: int) -> List[int]:
    candidates: List[int] = []
    for p in [preferred, 5000, 5705, 5706, 5707, 5710, 5711, 5712, 5713, 5714, 5715]:
        if p > 0 and p not in candidates:
            candidates.append(p)
    return candidates

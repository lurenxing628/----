from __future__ import annotations

import ipaddress
import logging
import os
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


def pick_port(host: str, preferred: int, *, logger: logging.Logger | None = None) -> tuple[str, int]:
    candidates: list[int] = []
    for p in [preferred, 5000, 5705, 5706, 5707, 5710, 5711, 5712, 5713, 5714, 5715]:
        try:
            p0 = int(p)
        except Exception:
            continue
        if p0 <= 0:
            continue
        if p0 not in candidates:
            candidates.append(p0)

    fallback_host = "127.0.0.1"
    for p in candidates:
        if _can_bind(host, p):
            return (host, int(p))

    if host != fallback_host:
        for p in candidates:
            if _can_bind(fallback_host, p):
                return (fallback_host, int(p))

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


def _normalize_db_path_for_runtime(db_path: str | None) -> str:
    raw = str(db_path or "").strip()
    if not raw:
        return ""
    return os.path.normcase(os.path.abspath(raw))


def write_runtime_host_port_files(
    runtime_dir: str,
    cfg_log_dir: str | None,
    host: str,
    port: int,
    db_path: str | None = None,
    *,
    logger: logging.Logger | None = None,
) -> None:
    runtime_log_dir = os.path.join(runtime_dir, "logs")
    os.makedirs(runtime_log_dir, exist_ok=True)
    port_file = os.path.join(runtime_log_dir, "aps_port.txt")
    host_file = os.path.join(runtime_log_dir, "aps_host.txt")
    db_file = os.path.join(runtime_log_dir, "aps_db_path.txt")

    with open(port_file, "w", encoding="utf-8") as f:
        f.write(str(int(port)) + "\n")

    host_for_client = (str(host or "").strip() or "127.0.0.1")
    if host_for_client == "0.0.0.0":
        host_for_client = "127.0.0.1"
    with open(host_file, "w", encoding="utf-8") as f:
        f.write(str(host_for_client) + "\n")

    db_for_runtime = _normalize_db_path_for_runtime(db_path)
    with open(db_file, "w", encoding="utf-8") as f:
        f.write(db_for_runtime + "\n")

    cfg_log_dir_s = ""
    try:
        cfg_log_dir_s = str(cfg_log_dir).strip() if cfg_log_dir is not None else ""
    except Exception:
        cfg_log_dir_s = ""
    if cfg_log_dir_s:
        try:
            if os.path.abspath(cfg_log_dir_s) != os.path.abspath(runtime_log_dir):
                os.makedirs(cfg_log_dir_s, exist_ok=True)
                mirror_port_file = os.path.join(cfg_log_dir_s, "aps_port.txt")
                with open(mirror_port_file, "w", encoding="utf-8") as f2:
                    f2.write(str(int(port)) + "\n")
                mirror_host_file = os.path.join(cfg_log_dir_s, "aps_host.txt")
                with open(mirror_host_file, "w", encoding="utf-8") as f3:
                    f3.write(str(host_for_client) + "\n")
                mirror_db_file = os.path.join(cfg_log_dir_s, "aps_db_path.txt")
                with open(mirror_db_file, "w", encoding="utf-8") as f4:
                    f4.write(db_for_runtime + "\n")
        except Exception:
            pass

    if logger is not None:
        try:
            logger.info(f"端口已写入：{port_file} -> {int(port)}")
            logger.info(f"Host 已写入：{host_file} -> {host_for_client}")
            logger.info(f"DB 路径已写入：{db_file} -> {db_for_runtime}")
        except Exception:
            pass


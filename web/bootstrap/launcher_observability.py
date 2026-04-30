from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

LAUNCHER_LOG_FILE = "launcher.log"
RUNTIME_ERROR_FILE = "aps_launch_error.txt"


@dataclass(frozen=True)
class LauncherLogResult:
    logger_ok: bool
    file_ok: bool
    error_file_ok: bool
    stderr_ok: bool
    attempted_paths: Tuple[str, ...]
    errors: Tuple[str, ...]


def launcher_log_warning(
    logger: Optional[Any],
    message: str,
    *args: Any,
    runtime_dir: Optional[str] = None,
    state_dir: Optional[str] = None,
    cfg_log_dir: Optional[str] = None,
    write_launch_error: bool = False,
) -> LauncherLogResult:
    text = _format_message(message, *args)
    attempted_paths: List[str] = []
    errors: List[str] = []

    logger_ok = _write_logger_warning(logger, text, errors)
    target_dir = _resolve_log_target_dir(runtime_dir=runtime_dir, state_dir=state_dir, cfg_log_dir=cfg_log_dir)
    file_ok = False
    error_file_ok = False
    if target_dir:
        file_ok = _append_text_file(os.path.join(target_dir, LAUNCHER_LOG_FILE), _format_file_line(text), attempted_paths, errors)
        if write_launch_error:
            error_file_ok = _write_text_file(os.path.join(target_dir, RUNTIME_ERROR_FILE), text.rstrip() + "\n", attempted_paths, errors)

    stderr_ok = False
    if not logger_ok or not file_ok or (write_launch_error and not error_file_ok):
        stderr_ok = _write_stderr(text, errors)
    return LauncherLogResult(
        logger_ok=logger_ok,
        file_ok=file_ok,
        error_file_ok=error_file_ok,
        stderr_ok=stderr_ok,
        attempted_paths=tuple(attempted_paths),
        errors=tuple(errors),
    )


def _format_message(message: str, *args: Any) -> str:
    text = str(message)
    if not args:
        return text
    try:
        return text % args
    except Exception:
        return f"{text} | args={args!r}"


def _format_file_line(text: str) -> str:
    return "{} [WARNING] {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), text)


def _write_logger_warning(logger: Optional[Any], text: str, errors: List[str]) -> bool:
    method = getattr(logger, "warning", None) if logger is not None else None
    if not callable(method):
        return False
    try:
        method("%s", text)
        return True
    except Exception as exc:
        errors.append(f"logger:{exc}")
        return False


def _resolve_log_target_dir(
    *,
    runtime_dir: Optional[str],
    state_dir: Optional[str],
    cfg_log_dir: Optional[str],
) -> str:
    for candidate in (state_dir, cfg_log_dir):
        normalized = _normalize_dir(candidate)
        if normalized:
            return normalized
    runtime_dir_s = _normalize_dir(runtime_dir)
    if not runtime_dir_s:
        return ""
    if os.path.basename(runtime_dir_s).strip().lower() == "logs":
        return runtime_dir_s
    return os.path.join(runtime_dir_s, "logs")


def _normalize_dir(path: Optional[str]) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    return os.path.abspath(raw)


def _append_text_file(path: str, text: str, attempted_paths: List[str], errors: List[str]) -> bool:
    attempted_paths.append(path)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
        return True
    except Exception as exc:
        errors.append(f"{path}:{exc}")
        return False


def _write_text_file(path: str, text: str, attempted_paths: List[str], errors: List[str]) -> bool:
    attempted_paths.append(path)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return True
    except Exception as exc:
        errors.append(f"{path}:{exc}")
        return False


def _write_stderr(text: str, errors: List[str]) -> bool:
    try:
        print(text, file=sys.stderr)
        return True
    except Exception as exc:
        errors.append(f"stderr:{exc}")
        return False


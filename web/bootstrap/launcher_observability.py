"""启动期落盘：还没有应用日志器时，把启动阶段与启动失败写进 launcher.log 和 aps_launch_error.txt。

`app.py` 记录入口模块导入失败也走这里，所以本模块只依赖标准库日志底座与固定文件写入，
不能引入数据库、事务、Flask 或服务层。启动器（aps-launcher.ps1）靠错误文件的新修改时间判定启动失败。
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

from core.infrastructure.logging import format_log_message, write_stderr
from core.infrastructure.safe_files import write_fixed_text

LAUNCHER_LOG_FILE = "launcher.log"
RUNTIME_ERROR_FILE = "aps_launch_error.txt"


def launcher_log_warning(
    logger: Optional[logging.Logger],
    message: str,
    *args: Any,
    runtime_dir: Optional[str] = None,
    state_dir: Optional[str] = None,
    cfg_log_dir: Optional[str] = None,
    logger_level: str = "warning",
) -> None:
    """写一行启动日志：有日志器先写日志器，再追加 launcher.log；没有日志器或文件写不进时写 stderr。"""
    text = format_log_message(message, *args)
    if logger is not None:
        getattr(logger, logger_level)("%s", text)
    target_dir = _resolve_log_target_dir(runtime_dir=runtime_dir, state_dir=state_dir, cfg_log_dir=cfg_log_dir)
    file_ok = bool(target_dir) and _write_launch_file(
        os.path.join(target_dir, LAUNCHER_LOG_FILE), _format_file_line(text, level=logger_level), append=True
    )
    if logger is None or not file_ok:
        write_stderr(text)


def write_launch_error(
    logger: Optional[logging.Logger],
    message: str,
    *args: Any,
    state_dir: Optional[str],
    public_message: str,
    runtime_dir: Optional[str] = None,
) -> None:
    """启动失败留痕：详细原因追加进 launcher.log，公开提示覆写 aps_launch_error.txt。

    两份文件各自尝试，前一份写失败不跳过后一份；提示文件没写成而日志写成时，在日志里补记一行。
    没有日志器或任一文件写不进时，把公开提示写到 stderr。
    """
    text = format_log_message(message, *args)
    if logger is not None:
        logger.error("%s", text)
    target_dir = _resolve_log_target_dir(runtime_dir=runtime_dir, state_dir=state_dir, cfg_log_dir=None)
    file_ok = error_file_ok = False
    if target_dir:
        file_ok = _write_launch_file(
            os.path.join(target_dir, LAUNCHER_LOG_FILE), _format_file_line(text, level="error"), append=True
        )
        error_file_ok = _write_launch_file(
            os.path.join(target_dir, RUNTIME_ERROR_FILE), public_message.rstrip() + "\n", append=False
        )
    if logger is None or not file_ok or not error_file_ok:
        write_stderr(public_message)
    if file_ok and not error_file_ok:
        launcher_log_warning(
            logger, "写入启动错误提示文件失败。", runtime_dir=runtime_dir, state_dir=state_dir, logger_level="error"
        )


def _format_file_line(text: str, *, level: str) -> str:
    return "{} [{}] {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), level.upper(), text)


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


def _write_launch_file(path: str, text: str, *, append: bool) -> bool:
    try:
        write_fixed_text(path, text, append=append)
    except (OSError, UnicodeEncodeError):
        return False
    return True

"""运行日志页与诊断包导出（/system/runtime-logs*）。

「运行日志」= logs/ 下的文件日志（程序自动产生），与「操作日志」（OperationLogs 表，
业务审计）严格区分。本页只读不删：报错证据不许销毁（轮转管大小）。
"""

from __future__ import annotations

import os
import platform
import sys
import tempfile
from datetime import datetime
from typing import Dict, List

from flask import current_app, flash, g, redirect, render_template, request, send_file, url_for

from config import Config
from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION
from core.services.system.runtime_log_reader import (
    LOG_FILE_CHOICES,
    MAX_ENTRIES,
    build_diagnostic_zip,
    read_log_entries_tail,
)

from .system_bp import bp
from .system_utils import _get_operation_log_service

_LEVEL_FILTER_CHOICES = ("", "ERROR", "WARNING")
_OPERATION_LOG_EXPORT_LIMIT = 200


@bp.get("/runtime-logs")
def runtime_logs_page():
    file_raw = request.args.get("file") or ""
    if file_raw and file_raw not in LOG_FILE_CHOICES:
        # 白名单严格相等匹配：非法值（含目录遍历尝试）明示并回默认，不发生文件读取
        flash("未知的日志文件，已切换到默认的报错日志。", "warning")
        return redirect(url_for("system.runtime_logs_page"))
    selected_file = file_raw or LOG_FILE_CHOICES[0]

    level_raw = (request.args.get("level") or "").strip().upper()
    level = level_raw if level_raw in _LEVEL_FILTER_CHOICES else ""
    keyword = (request.args.get("q") or "").strip()

    log_path = os.path.join(current_app.config["LOG_DIR"], selected_file)
    read_error = None
    entries: List[Dict[str, str]] = []
    try:
        entries = read_log_entries_tail(log_path)
    except OSError as e:
        # 不吞错契约：读取失败页面明示原因，不渲染假空态
        read_error = str(e)
        current_app.logger.error("运行日志读取失败 %s：%s", log_path, e)

    total_before_filter = len(entries)
    entries = _apply_entry_filters(entries, level, keyword)

    return render_template(
        "system/runtime_logs.html",
        title="系统管理 - 运行日志",
        entries=entries,
        selected_file=selected_file,
        file_choices=LOG_FILE_CHOICES,
        file_exists=os.path.exists(log_path),
        read_error=read_error,
        max_entries=MAX_ENTRIES,
        total_before_filter=total_before_filter,
        filters={"level": level, "q": keyword},
    )


def _apply_entry_filters(
    entries: List[Dict[str, str]], level: str, keyword: str
) -> List[Dict[str, str]]:
    if level:
        entries = [e for e in entries if e["level"] == level]
    if keyword:
        entries = [e for e in entries if keyword in e["head"] or keyword in e["body"]]
    return entries


@bp.get("/runtime-logs/diagnostic-package")
def runtime_logs_diagnostic_package():
    log_dir = current_app.config["LOG_DIR"]
    operation_logs_text, operation_logs_arcname = _collect_operation_logs_text()

    # mkstemp 返回已打开的 fd——立即关闭释放句柄（zipfile 自己重开路径写，
    # Windows 下不关会让后续打开/删除撞句柄占用）
    fd, zip_path = tempfile.mkstemp(prefix="aps_diagnostic_", suffix=".zip")
    os.close(fd)
    try:
        build_diagnostic_zip(
            log_dir,
            zip_path,
            operation_logs_text=operation_logs_text,
            info_text=_build_diagnostic_info_text(),
            operation_logs_arcname=operation_logs_arcname,
        )
        download_name = "aps_诊断包_{}.zip".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
        response = send_file(
            zip_path,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/zip",
        )
        # send_file 默认 direct_passthrough：WSGI 拿到的是裸文件包装器，响应对象的
        # close 链（call_on_close 回调）不会触发，临时文件必泄漏。关掉它让响应体走
        # ClosingIterator——先关文件句柄再跑回调（删除顺序对 Windows 正确），代价只是
        # 分块 Python 读，本地单用户部署可接受。
        response.direct_passthrough = False
    except Exception as e:
        # 构包/响应装配失败：当场清理临时文件，flash 明示后回页面
        _remove_quietly(zip_path, current_app.logger)
        current_app.logger.error("诊断包导出失败：%s", e)
        flash(f"诊断包导出失败：{e}", "error")
        return redirect(url_for("system.runtime_logs_page"))

    # 下载成功路径：响应流真正关闭后才能删（普通 finally 在响应对象返回时就触发，
    # Windows 下文件正被响应流持有）；孤儿临时文件是可容忍降级，删除失败只 warning。
    # 回调执行时应用上下文可能已退出，logger 引用现在捕获，不在回调里碰 current_app。
    cleanup_logger = current_app.logger
    response.call_on_close(lambda: _remove_quietly(zip_path, cleanup_logger))

    if getattr(g, "op_logger", None) is not None:
        g.op_logger.info(
            module="system",
            action="diagnostic_export",
            target_type="diagnostic_package",
            target_id=download_name,
            detail={"log_dir_files": "whitelist", "operation_logs_included": operation_logs_arcname},
        )
    return response


def _collect_operation_logs_text():
    """最近 200 条操作日志纯文本。读取失败时返回说明文本+失败命名的 arcname——
    诊断包是排障工具，部分缺失好过整体失败，但缺失必须在包内明示。"""
    try:
        items = _get_operation_log_service().list_recent(limit=_OPERATION_LOG_EXPORT_LIMIT)
    except Exception as e:
        current_app.logger.error("诊断包附操作日志读取失败：%s", e)
        return (
            f"操作日志读取失败，本文件代替说明。\n失败原因：{e}\n",
            "operation_logs_读取失败.txt",
        )
    lines = [f"最近 {len(items)} 条操作日志（新→旧）：", ""]
    for log in items:
        lines.append(
            "{} [{}] {}/{} target={}:{} operator={} detail={} error={}".format(
                log.log_time or "-",
                log.log_level,
                log.module,
                log.action,
                log.target_type or "-",
                log.target_id or "-",
                log.operator or "-",
                log.detail or "-",
                log.error_message or "-",
            )
        )
    return "\n".join(lines) + "\n", "operation_logs.txt"


def _build_diagnostic_info_text() -> str:
    """环境信息拼现有事实（全仓无 APP_VERSION 常量，不新立版本号体系）。"""
    from web.routes.system_health import _CONTRACT_VERSION

    return (
        f"应用：{Config.APP_NAME}\n"
        f"数据库 Schema 版本：{CURRENT_SCHEMA_VERSION}\n"
        f"健康检查契约版本：{_CONTRACT_VERSION}\n"
        f"Python：{sys.version.splitlines()[0]}\n"
        f"平台：{platform.platform()}\n"
        f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )


def _remove_quietly(path: str, logger) -> None:
    try:
        os.remove(path)
    except OSError as e:
        logger.warning("诊断包临时文件清理失败（可容忍，等系统临时目录回收）：%s", e)

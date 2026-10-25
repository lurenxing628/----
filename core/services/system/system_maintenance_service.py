from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from core.infrastructure.backup import MIN_KEEP_BACKUPS
from core.infrastructure.logging import safe_log
from core.models.enums import YesNo
from core.models.system_job_state import SystemJobState
from core.services.system.maintenance.backup_task import maybe_run_auto_backup
from core.services.system.maintenance.cleanup_task import maybe_run_auto_backup_cleanup, maybe_run_auto_log_cleanup
from core.services.system.maintenance.throttle import MaintenanceThrottle
from data.repositories import SystemJobStateRepository

from .system_config_service import SystemConfigService


@dataclass(frozen=True)
class ParsedJobTime:
    value: Optional[datetime]
    state: str
    raw: Optional[str] = None


def _parse_db_dt(value: Optional[str]) -> ParsedJobTime:
    raw = None if value is None else str(value)
    if raw is None:
        return ParsedJobTime(value=None, state="missing", raw=None)
    v = raw.strip().replace("：", ":")
    if not v:
        return ParsedJobTime(value=None, state="missing", raw=raw)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return ParsedJobTime(value=datetime.strptime(v, fmt), state="valid", raw=v)
        except ValueError:
            continue
    return ParsedJobTime(value=None, state="invalid", raw=raw)


def _fmt_db_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class SystemMaintenanceService:
    """
    系统维护（访问完成后，由现有运行线程在空闲时检查）。

    目标：
    - 分钟级自动备份
    - 分钟级自动清理备份文件（保留策略）
    - 分钟级自动清理操作日志（保留策略，避免过度清理）

    约束：
    - 不另启维护线程，复用宿主已有的运行线程
    - 轻量：加进程内节流，避免每个请求都做 DB 查询/文件扫描
    """

    # 进程内节流：避免静态资源/频繁刷新导致重复检查
    CHECK_THROTTLE_SECONDS = 10

    # 清理限额（避免一次请求删太多）
    MAX_BACKUP_DELETE_PER_RUN = 200
    MAX_LOG_DELETE_PER_RUN = 2000
    MIN_KEEP_LOGS = 50  # 至少保留最近 N 条日志，避免过度清理
    MIN_KEEP_BACKUPS = MIN_KEEP_BACKUPS  # 至少保留最新 N 份备份，keep_days 修剪不越过该保底（B01）

    JOB_AUTO_BACKUP = "auto_backup"
    JOB_AUTO_BACKUP_CLEANUP = "auto_backup_cleanup"
    JOB_AUTO_LOG_CLEANUP = "auto_log_cleanup"

    @classmethod
    def run_if_due(
        cls,
        conn,
        *,
        db_path: str,
        backup_dir: str,
        backup_keep_days_default: int,
        logger=None,
        op_logger=None,
        admission_window=None,
    ) -> None:
        if not MaintenanceThrottle.allow_run(cls.CHECK_THROTTLE_SECONDS):
            return

        cfg_svc = SystemConfigService(conn, logger=logger)
        cfg = cfg_svc.get_snapshot_readonly(backup_keep_days_default=int(backup_keep_days_default))
        job_repo = SystemJobStateRepository(conn, logger=logger)
        job_states = None

        now = datetime.now()
        with ExitStack() as ownership:
            admitted = False

            def is_due(repo: SystemJobStateRepository, job_key: str, current: datetime, interval_minutes: int) -> bool:
                nonlocal admitted, job_states
                if job_states is None:
                    job_states = {item.job_key: item for item in repo.list_all()}
                captured = cls._is_due(job_states.get(job_key), current, interval_minutes)
                if captured and admission_window is not None and not admitted:
                    ownership.enter_context(admission_window())
                    admitted = True
                return captured

            # -------------------------
            # 1) 自动备份
            # -------------------------
            auto_backup_failed_this_round = False
            if cfg.auto_backup_enabled == YesNo.YES.value:
                due, ok = maybe_run_auto_backup(
                    conn,
                    job_repo=job_repo,
                    now=now,
                    interval_minutes=int(cfg.auto_backup_interval_minutes),
                    db_path=db_path,
                    backup_dir=backup_dir,
                    keep_days=int(cfg.auto_backup_keep_days),
                    job_key=cls.JOB_AUTO_BACKUP,
                    logger=logger,
                    op_logger=op_logger,
                    is_due_fn=is_due,
                    fmt_db_dt_fn=_fmt_db_dt,
                )
                # 到期但备份失败时，保留现有好备份，阻止本轮清理。
                auto_backup_failed_this_round = due and not ok

            # -------------------------
            # 2) 自动清理备份（保留策略）
            # -------------------------
            if cfg.auto_backup_cleanup_enabled == YesNo.YES.value:
                if auto_backup_failed_this_round:
                    # B01(2)：当轮自动备份失败时跳过本轮自动清理——没有新的好备份落地时
                    # 不修剪历史备份，避免『备份失败 + 清理照跑』把仅存的好备份删光。
                    # 不写 cleanup job_state，下一轮备份成功后清理照常恢复执行。
                    safe_log(
                        logger,
                        "warning",
                        "本轮自动备份失败，已跳过本轮自动清理备份（reason=auto_backup_failed_this_round，"
                        "失败原因见 auto_backup 的 error 日志与 OperationLogs）。",
                    )
                else:
                    maybe_run_auto_backup_cleanup(
                        conn,
                        job_repo=job_repo,
                        now=now,
                        interval_minutes=int(cfg.auto_backup_cleanup_interval_minutes),
                        backup_dir=backup_dir,
                        keep_days=int(cfg.auto_backup_keep_days),
                        max_backup_delete_per_run=int(cls.MAX_BACKUP_DELETE_PER_RUN),
                        job_key=cls.JOB_AUTO_BACKUP_CLEANUP,
                        logger=logger,
                        op_logger=op_logger,
                        is_due_fn=is_due,
                        fmt_db_dt_fn=_fmt_db_dt,
                        min_keep_backups=int(cls.MIN_KEEP_BACKUPS),
                    )

            # -------------------------
            # 3) 自动清理操作日志（保留策略）
            # -------------------------
            if cfg.auto_log_cleanup_enabled == YesNo.YES.value:
                maybe_run_auto_log_cleanup(
                    conn,
                    job_repo=job_repo,
                    now=now,
                    interval_minutes=int(cfg.auto_log_cleanup_interval_minutes),
                    keep_days=int(cfg.auto_log_cleanup_keep_days),
                    min_keep_logs=int(cls.MIN_KEEP_LOGS),
                    max_log_delete_per_run=int(cls.MAX_LOG_DELETE_PER_RUN),
                    job_key=cls.JOB_AUTO_LOG_CLEANUP,
                    logger=logger,
                    op_logger=op_logger,
                    is_due_fn=is_due,
                    fmt_db_dt_fn=_fmt_db_dt,
                )
    # -------------------------
    # 内部辅助方法
    # -------------------------
    @classmethod
    def _is_due(cls, st: Optional[SystemJobState], now: datetime, interval_minutes: int) -> bool:
        parsed = _parse_db_dt(st.last_run_time if st else None)
        if parsed.state != "valid" or parsed.value is None:
            return True
        delta = now - parsed.value
        return delta >= timedelta(minutes=int(interval_minutes))

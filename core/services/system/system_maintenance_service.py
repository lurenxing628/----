from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from core.models.enums import YesNo
from data.repositories import SystemJobStateRepository

from .maintenance import (
    MaintenanceThrottle,
    maybe_run_auto_backup,
    maybe_run_auto_backup_cleanup,
    maybe_run_auto_log_cleanup,
)
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
        except Exception:
            continue
    return ParsedJobTime(value=None, state="invalid", raw=raw)


def _fmt_db_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class MaintenanceResult:
    ran_any: bool
    details: Dict[str, Any]


class SystemMaintenanceService:
    """
    系统维护（按请求触发）。

    目标：
    - 分钟级自动备份
    - 分钟级自动清理备份文件（保留策略）
    - 分钟级自动清理操作日志（保留策略，避免过度清理）

    约束：
    - 不启后台线程
    - 轻量：加进程内节流，避免每个请求都做 DB 查询/文件扫描
    """

    # 进程内节流：避免静态资源/频繁刷新导致重复检查
    CHECK_THROTTLE_SECONDS = 10

    # 清理限额（避免一次请求删太多）
    MAX_BACKUP_DELETE_PER_RUN = 200
    MAX_LOG_DELETE_PER_RUN = 2000
    MIN_KEEP_LOGS = 50  # 至少保留最近 N 条日志，避免过度清理

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
    ) -> MaintenanceResult:
        if not MaintenanceThrottle.allow_run(cls.CHECK_THROTTLE_SECONDS):
            return MaintenanceResult(ran_any=False, details={"throttled": True})

        cfg_svc = SystemConfigService(conn, logger=logger)
        cfg = cfg_svc.get_snapshot(backup_keep_days_default=int(backup_keep_days_default))
        job_repo = SystemJobStateRepository(conn, logger=logger)

        now = datetime.now()
        details: Dict[str, Any] = {"throttled": False, "now": _fmt_db_dt(now)}
        ran_any = False

        # -------------------------
        # 1) 自动备份
        # -------------------------
        if cfg.auto_backup_enabled == YesNo.YES.value:
            ran, d = maybe_run_auto_backup(
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
                is_due_fn=cls._is_due,
                fmt_db_dt_fn=_fmt_db_dt,
            )
            details["auto_backup"] = d
            ran_any = ran_any or ran

        # -------------------------
        # 2) 自动清理备份（保留策略）
        # -------------------------
        if cfg.auto_backup_cleanup_enabled == YesNo.YES.value:
            ran, d = maybe_run_auto_backup_cleanup(
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
                is_due_fn=cls._is_due,
                fmt_db_dt_fn=_fmt_db_dt,
            )
            details["auto_backup_cleanup"] = d
            ran_any = ran_any or ran

        # -------------------------
        # 3) 自动清理操作日志（保留策略）
        # -------------------------
        if cfg.auto_log_cleanup_enabled == YesNo.YES.value:
            ran, d = maybe_run_auto_log_cleanup(
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
                is_due_fn=cls._is_due,
                fmt_db_dt_fn=_fmt_db_dt,
            )
            details["auto_log_cleanup"] = d
            ran_any = ran_any or ran

        return MaintenanceResult(ran_any=ran_any, details=details)

    # -------------------------
    # Internal helpers
    # -------------------------
    @classmethod
    def _is_due(cls, job_repo: SystemJobStateRepository, job_key: str, now: datetime, interval_minutes: int) -> Tuple[bool, Optional[str], str, Optional[str]]:
        st = job_repo.get(job_key)
        parsed = _parse_db_dt(st.last_run_time if st else None)
        if parsed.state != "valid" or parsed.value is None:
            return True, None, parsed.state, parsed.raw
        delta = now - parsed.value
        return delta >= timedelta(minutes=int(interval_minutes)), _fmt_db_dt(parsed.value), parsed.state, parsed.raw

    @classmethod
    def reset_throttle_for_tests(cls) -> None:
        MaintenanceThrottle.reset()


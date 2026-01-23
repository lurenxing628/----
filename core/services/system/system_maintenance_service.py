from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from core.infrastructure.backup import BackupManager
from data.repositories import SystemJobStateRepository

from .system_config_service import SystemConfigService


def _parse_db_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    v = str(value).strip()
    if not v:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(v, fmt)
        except Exception:
            continue
    # 兜底：解析失败就当作“从未运行”
    return None


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
    _last_check_ts: float = 0.0

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
        now_ts = time.time()
        if (now_ts - cls._last_check_ts) < cls.CHECK_THROTTLE_SECONDS:
            return MaintenanceResult(ran_any=False, details={"throttled": True})
        cls._last_check_ts = now_ts

        cfg_svc = SystemConfigService(conn, logger=logger)
        cfg = cfg_svc.get_snapshot(backup_keep_days_default=int(backup_keep_days_default))
        job_repo = SystemJobStateRepository(conn, logger=logger)

        now = datetime.now()
        details: Dict[str, Any] = {"throttled": False, "now": _fmt_db_dt(now)}
        ran_any = False

        # -------------------------
        # 1) 自动备份
        # -------------------------
        if cfg.auto_backup_enabled == "yes":
            ran, d = cls._maybe_run_auto_backup(
                conn,
                job_repo=job_repo,
                now=now,
                interval_minutes=int(cfg.auto_backup_interval_minutes),
                db_path=db_path,
                backup_dir=backup_dir,
                keep_days=int(cfg.auto_backup_keep_days),
                logger=logger,
                op_logger=op_logger,
            )
            details["auto_backup"] = d
            ran_any = ran_any or ran

        # -------------------------
        # 2) 自动清理备份（保留策略）
        # -------------------------
        if cfg.auto_backup_cleanup_enabled == "yes":
            ran, d = cls._maybe_run_auto_backup_cleanup(
                conn,
                job_repo=job_repo,
                now=now,
                interval_minutes=int(cfg.auto_backup_cleanup_interval_minutes),
                backup_dir=backup_dir,
                keep_days=int(cfg.auto_backup_keep_days),
                logger=logger,
                op_logger=op_logger,
            )
            details["auto_backup_cleanup"] = d
            ran_any = ran_any or ran

        # -------------------------
        # 3) 自动清理操作日志（保留策略）
        # -------------------------
        if cfg.auto_log_cleanup_enabled == "yes":
            ran, d = cls._maybe_run_auto_log_cleanup(
                conn,
                job_repo=job_repo,
                now=now,
                interval_minutes=int(cfg.auto_log_cleanup_interval_minutes),
                keep_days=int(cfg.auto_log_cleanup_keep_days),
                logger=logger,
                op_logger=op_logger,
            )
            details["auto_log_cleanup"] = d
            ran_any = ran_any or ran

        return MaintenanceResult(ran_any=ran_any, details=details)

    # -------------------------
    # Internal helpers
    # -------------------------
    @classmethod
    def _is_due(cls, job_repo: SystemJobStateRepository, job_key: str, now: datetime, interval_minutes: int) -> Tuple[bool, Optional[str]]:
        st = job_repo.get(job_key)
        last = _parse_db_dt(st.last_run_time) if st else None
        if last is None:
            return True, None
        delta = now - last
        return delta >= timedelta(minutes=int(interval_minutes)), _fmt_db_dt(last)

    @classmethod
    def _maybe_run_auto_backup(
        cls,
        conn,
        *,
        job_repo: SystemJobStateRepository,
        now: datetime,
        interval_minutes: int,
        db_path: str,
        backup_dir: str,
        keep_days: int,
        logger=None,
        op_logger=None,
    ) -> Tuple[bool, Dict[str, Any]]:
        due, last_run = cls._is_due(job_repo, cls.JOB_AUTO_BACKUP, now, interval_minutes)
        if not due:
            return False, {"due": False, "last_run_time": last_run}

        mgr = BackupManager(db_path=db_path, backup_dir=backup_dir, keep_days=int(keep_days), logger=logger)
        try:
            path = mgr.backup(suffix="auto")
            filename = os.path.basename(path)
            size_mb = None
            try:
                size_mb = round(os.stat(path).st_size / 1024 / 1024, 2)
            except Exception:
                size_mb = None

            if op_logger is not None:
                op_logger.info(
                    module="system",
                    action="backup",
                    target_type="backup",
                    target_id=filename,
                    detail={"filename": filename, "suffix": "auto", "size_mb": size_mb, "mode": "auto"},
                )

            job_repo.set_last_run(
                cls.JOB_AUTO_BACKUP,
                last_run_time=_fmt_db_dt(now),
                last_run_detail=json.dumps({"filename": filename, "size_mb": size_mb}, ensure_ascii=False),
            )
            return True, {"due": True, "created": filename}
        except Exception as e:
            if logger:
                logger.error(f"自动备份失败：{e}")
            return False, {"due": True, "error": str(e)}

    @classmethod
    def _cleanup_backups_with_limit(cls, backup_dir: str, keep_days: int, max_delete: int) -> Tuple[int, Dict[str, Any]]:
        cutoff = datetime.now() - timedelta(days=int(keep_days))
        if not os.path.exists(backup_dir):
            return 0, {"cutoff": _fmt_db_dt(cutoff), "reason": "backup_dir_not_exists"}

        candidates = []
        for fn in os.listdir(backup_dir):
            if not fn.startswith("aps_backup_") or not fn.endswith(".db"):
                continue
            fp = os.path.join(backup_dir, fn)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fp))
            except Exception:
                continue
            if mtime < cutoff:
                candidates.append((mtime, fn, fp))

        candidates.sort(key=lambda x: x[0])  # 先删最旧的
        removed = 0
        removed_sample = []
        for _, fn, fp in candidates[: int(max_delete)]:
            try:
                os.remove(fp)
                removed += 1
                if len(removed_sample) < 10:
                    removed_sample.append(fn)
            except Exception:
                continue

        return removed, {"cutoff": _fmt_db_dt(cutoff), "candidates": len(candidates), "removed_sample": removed_sample}

    @classmethod
    def _maybe_run_auto_backup_cleanup(
        cls,
        conn,
        *,
        job_repo: SystemJobStateRepository,
        now: datetime,
        interval_minutes: int,
        backup_dir: str,
        keep_days: int,
        logger=None,
        op_logger=None,
    ) -> Tuple[bool, Dict[str, Any]]:
        due, last_run = cls._is_due(job_repo, cls.JOB_AUTO_BACKUP_CLEANUP, now, interval_minutes)
        if not due:
            return False, {"due": False, "last_run_time": last_run}

        try:
            removed, meta = cls._cleanup_backups_with_limit(
                backup_dir=str(backup_dir),
                keep_days=int(keep_days),
                max_delete=int(cls.MAX_BACKUP_DELETE_PER_RUN),
            )
            if op_logger is not None:
                op_logger.info(
                    module="system",
                    action="cleanup",
                    target_type="backup",
                    target_id=None,
                    detail={
                        "mode": "auto",
                        "keep_days": int(keep_days),
                        "removed_count": int(removed),
                        "max_delete_per_run": int(cls.MAX_BACKUP_DELETE_PER_RUN),
                        **meta,
                    },
                )
            job_repo.set_last_run(
                cls.JOB_AUTO_BACKUP_CLEANUP,
                last_run_time=_fmt_db_dt(now),
                last_run_detail=json.dumps({"removed_count": removed, **meta}, ensure_ascii=False),
            )
            return True, {"due": True, "removed_count": int(removed), **meta}
        except Exception as e:
            if logger:
                logger.error(f"自动清理备份失败：{e}")
            return False, {"due": True, "error": str(e)}

    @classmethod
    def _cleanup_operation_logs_with_limit(
        cls,
        conn,
        *,
        keep_days: int,
        min_keep_logs: int,
        max_delete: int,
    ) -> Tuple[int, Dict[str, Any]]:
        total = conn.execute("SELECT COUNT(1) FROM OperationLogs").fetchone()[0]
        if int(total) <= int(min_keep_logs):
            return 0, {"total": int(total), "skipped": True, "reason": "total_le_min_keep"}

        cutoff_dt = datetime.now() - timedelta(days=int(keep_days))
        cutoff = _fmt_db_dt(cutoff_dt)

        cand = conn.execute("SELECT COUNT(1) FROM OperationLogs WHERE log_time < ?", (cutoff,)).fetchone()[0]
        cand = int(cand)
        if cand <= 0:
            return 0, {"total": int(total), "cutoff": cutoff, "candidates": 0, "skipped": True, "reason": "no_candidates"}

        allow = min(int(max_delete), int(total) - int(min_keep_logs))
        to_delete = min(cand, allow)
        if to_delete <= 0:
            return 0, {"total": int(total), "cutoff": cutoff, "candidates": cand, "skipped": True, "reason": "allow_le_0"}

        conn.execute(
            """
            DELETE FROM OperationLogs
            WHERE id IN (
                SELECT id FROM OperationLogs
                WHERE log_time < ?
                ORDER BY log_time ASC, id ASC
                LIMIT ?
            )
            """,
            (cutoff, int(to_delete)),
        )
        return int(to_delete), {"total": int(total), "cutoff": cutoff, "candidates": cand, "allow": int(allow)}

    @classmethod
    def _maybe_run_auto_log_cleanup(
        cls,
        conn,
        *,
        job_repo: SystemJobStateRepository,
        now: datetime,
        interval_minutes: int,
        keep_days: int,
        logger=None,
        op_logger=None,
    ) -> Tuple[bool, Dict[str, Any]]:
        due, last_run = cls._is_due(job_repo, cls.JOB_AUTO_LOG_CLEANUP, now, interval_minutes)
        if not due:
            return False, {"due": False, "last_run_time": last_run}

        try:
            deleted, meta = cls._cleanup_operation_logs_with_limit(
                conn,
                keep_days=int(keep_days),
                min_keep_logs=int(cls.MIN_KEEP_LOGS),
                max_delete=int(cls.MAX_LOG_DELETE_PER_RUN),
            )
            if op_logger is not None:
                op_logger.info(
                    module="system",
                    action="logs_cleanup",
                    target_type="operation_log",
                    target_id=None,
                    detail={
                        "mode": "auto",
                        "keep_days": int(keep_days),
                        "deleted_count": int(deleted),
                        "min_keep_logs": int(cls.MIN_KEEP_LOGS),
                        "max_delete_per_run": int(cls.MAX_LOG_DELETE_PER_RUN),
                        **meta,
                    },
                )
            job_repo.set_last_run(
                cls.JOB_AUTO_LOG_CLEANUP,
                last_run_time=_fmt_db_dt(now),
                last_run_detail=json.dumps({"deleted_count": deleted, **meta}, ensure_ascii=False),
            )
            return True, {"due": True, "deleted_count": int(deleted), **meta}
        except Exception as e:
            if logger:
                logger.error(f"自动清理操作日志失败：{e}")
            return False, {"due": True, "error": str(e)}


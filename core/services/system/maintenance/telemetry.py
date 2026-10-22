"""Maintenance telemetry keeps each write in its own transaction."""

from core.infrastructure.logging import safe_log
from core.infrastructure.transaction import TransactionManager


def write_oplog(conn, *, op_logger, logger=None, level: str, **kwargs) -> bool:
    if op_logger is None:
        return True
    try:
        with TransactionManager(conn).transaction():
            if level == "error":
                result = op_logger.error(**kwargs)
            else:
                result = op_logger.info(**kwargs)
            if result is False:
                raise RuntimeError("OperationLogs 未成功落库。")
        return True
    except Exception as exc:
        safe_log(logger, "warning", f"系统维护 telemetry 写入 OperationLogs 失败：{exc}")
        return False


def write_job_state(conn, *, job_repo, job_key: str, last_run_time: str, last_run_detail: str, logger=None) -> bool:
    try:
        with TransactionManager(conn).transaction():
            job_repo.set_last_run(job_key, last_run_time=last_run_time, last_run_detail=last_run_detail)
        return True
    except Exception as exc:
        safe_log(logger, "warning", f"系统维护 telemetry 写入 SystemJobState 失败：{exc}")
        return False

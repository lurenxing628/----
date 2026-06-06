"""回归测试：_record_ortools_failure 记录 OR-Tools 预热失败时，即使 logger.warning 不支持 exc_info 参数也不二次崩溃——只调用一次 warning（含「OR-Tools 预热失败（已忽略）」与异常类型/消息），并把 ortools_warmstart_failed_count 计为 1。"""

from types import SimpleNamespace


class _StubLogger:
    """
    故意让 warning 不支持 exc_info 参数，用于验证记录失败信息时不会二次崩溃。
    """

    def __init__(self):
        self.warnings = []

    def warning(self, msg: str):
        self.warnings.append(str(msg))

    def info(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def exception(self, *args, **kwargs):
        return None


def test_optimizer_ortools_logging_exc_info_safe() -> None:

    from core.services.scheduler.run.schedule_optimizer_steps import _record_ortools_failure

    logger = _StubLogger()
    stats = {}
    try:
        raise RuntimeError("ortools boom (test)")
    except RuntimeError as exc:
        _record_ortools_failure(
            optimizer_algo_stats=stats,
            scheduler=SimpleNamespace(),
            logger=logger,
            exc=exc,
        )

    fallback_counts = stats.get("fallback_counts") or {}
    assert fallback_counts.get("ortools_warmstart_failed_count") == 1, stats
    assert len(logger.warnings) == 1, logger.warnings
    warning = logger.warnings[0]
    assert "OR-Tools 预热失败（已忽略）" in warning, warning
    assert "ortools boom (test)" in warning, warning
    assert "RuntimeError: ortools boom (test)" in warning, warning



import os
import sys
from types import SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

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
    print("OK")


if __name__ == "__main__":
    main()

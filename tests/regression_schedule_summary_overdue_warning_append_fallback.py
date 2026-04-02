import os
import sys
from datetime import datetime
from types import SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


class _StubSvc:
    logger = None

    @staticmethod
    def _normalize_text(value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.scheduler.schedule_summary import _build_overdue_items

    summary = SimpleNamespace(warnings=("已有告警",))
    items = _build_overdue_items(
        _StubSvc(),
        batches={"B_BAD": SimpleNamespace(due_date="2026-13-40")},
        finish_by_batch={},
        summary=summary,
    )

    assert items == [], f"非法 due_date 不应生成超期项：{items!r}"
    assert isinstance(summary.warnings, list), f"warnings 未被归一化为 list：{summary.warnings!r}"
    assert summary.warnings[0] == "已有告警", f"原有告警未保留：{summary.warnings!r}"
    assert any("due_date 格式不合法" in str(item) for item in summary.warnings), (
        f"非法 due_date 告警未写回 summary.warnings：{summary.warnings!r}"
    )

    print("OK")


if __name__ == "__main__":
    main()

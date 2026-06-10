"""回归测试：build_overdue_items 遇到批次的非法 due_date（如 2026-13-40）时不生成超期项，而是把 invalid_due_count、invalid_due_batch_ids_sample、invalid_due_raw_sample 写入 meta，并把"交期写法不对"告警追加写回 summary.warnings（原有告警保留，warnings 被归一化为 list）。"""

from datetime import datetime
from types import SimpleNamespace


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


def test_schedule_summary_overdue_warning_append_fallback() -> None:

    from core.services.scheduler.summary.schedule_summary import build_overdue_items

    summary = SimpleNamespace(warnings=("已有告警",))
    items, meta = build_overdue_items(
        _StubSvc(),
        batches={"B_BAD": SimpleNamespace(due_date="2026-13-40")},
        finish_by_batch={},
        summary=summary,
    )

    assert items == [], f"非法 due_date 不应生成超期项：{items!r}"
    assert int(meta.get("invalid_due_count") or 0) == 1, meta
    assert meta.get("invalid_due_batch_ids_sample") == ["B_BAD"], meta
    assert meta.get("invalid_due_raw_sample") == ["B_BAD='2026-13-40'"], meta

    assert isinstance(summary.warnings, list), f"warnings 未被归一化为 list：{summary.warnings!r}"
    assert summary.warnings[0] == "已有告警", f"原有告警未保留：{summary.warnings!r}"
    assert any("交期写法不对" in str(item) for item in summary.warnings), (
        f"非法 due_date 告警未写回 summary.warnings：{summary.warnings!r}"
    )



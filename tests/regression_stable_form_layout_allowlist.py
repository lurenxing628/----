from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_first_batch_pages_do_not_use_old_flex_filter_rows() -> None:
    for rel_path in (
        "templates/personnel/calendar.html",
        "templates/system/logs.html",
        "templates/reports/overdue.html",
        "templates/reports/utilization.html",
        "templates/reports/downtime.html",
        "templates/equipment/downtime_batch.html",
        "templates/scheduler/batches.html",
        "templates/scheduler/batches_manage.html",
        "web_new_test/templates/scheduler/batches.html",
        "web_new_test/templates/scheduler/batches_manage.html",
    ):
        source = _read(rel_path)
        assert "aps-filter-bar" not in source, rel_path
        assert "inline-flex-wrap" not in source, rel_path
        assert "form-row" not in source, rel_path


def main() -> None:
    test_first_batch_pages_do_not_use_old_flex_filter_rows()
    print("OK")


if __name__ == "__main__":
    main()

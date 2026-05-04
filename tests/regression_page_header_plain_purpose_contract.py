from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_priority_pages_use_plain_purpose_hero() -> None:
    pages = (
        "templates/personnel/teams.html",
        "templates/equipment/downtime_batch.html",
        "templates/system/history.html",
        "templates/reports/overdue.html",
        "templates/reports/utilization.html",
        "templates/reports/downtime.html",
    )
    for rel_path in pages:
        source = _read(rel_path)
        assert "ui.aps_page_hero" in source, f"{rel_path} 没有统一页头"
        assert "page-subtitle text-meta" not in source, f"{rel_path} 仍在用旧说明段"
        assert "aps-scenario-strip" not in source


def test_system_history_filter_is_not_inside_hero() -> None:
    source = _read("templates/system/history.html")
    hero_start = source.index("ui.aps_page_hero(")
    filter_start = source.index("筛选历史")
    assert hero_start < filter_start
    assert "aps-filter-grid" in source[filter_start:]
    assert "aps-filter-bar" not in source[:filter_start]


def main() -> None:
    test_priority_pages_use_plain_purpose_hero()
    test_system_history_filter_is_not_inside_hero()
    print("OK")


if __name__ == "__main__":
    main()

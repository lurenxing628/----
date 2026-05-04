from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_system_logs_uses_separate_cards_and_stable_filter_grid() -> None:
    source = _read("templates/system/logs.html")

    assert "inline-flex-wrap" not in source
    assert "日志自动清理设置" in source
    assert "筛选日志" in source
    assert "aps-settings-layout-card" in source
    assert "aps-settings-cleanup-grid" in source
    assert "aps-filter-grid" in source

    hero_start = source.index('<div class="card aps-page-hero">')
    hero_end = source.index("日志自动清理设置", hero_start)
    hero = source[hero_start:hero_end]
    for forbidden in ("日志自动清理设置", "筛选日志", "logsBatchDeleteForm"):
        assert forbidden not in hero

    for field_name in (
        "start_time",
        "end_time",
        "module",
        "action",
        "log_level",
        "limit",
        "auto_log_cleanup_enabled",
        "auto_log_cleanup_keep_days",
        "auto_log_cleanup_interval_minutes",
    ):
        assert f'name="{field_name}"' in source

    cleanup_start = source.index("日志自动清理设置")
    cleanup_end = source.index("筛选日志", cleanup_start)
    cleanup_block = source[cleanup_start:cleanup_end]
    assert cleanup_block.count("有人打开或操作页面时") == 1
    assert "aps-settings-cleanup-actions" in cleanup_block
    for marker in (
        "aps-settings-enable-field",
        "aps-settings-keep-days",
        "aps-settings-interval",
        "aps-settings-last-run",
    ):
        assert marker in cleanup_block

    css = _read("static/css/ui_contract.css")
    assert ".aps-settings-layout-card" in css
    assert "grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));" in css
    assert "@container (min-width: 760px)" in css

    result_start = source.index("查询结果")
    assert source.index('id="logsBatchDeleteForm"') > result_start
    assert 'name="log_ids"' in source
    assert 'form="logsBatchDeleteForm"' in source
    result_block = source[result_start:]
    assert '<input type="checkbox" class="js-log-select-all"' in result_block


def main() -> None:
    test_system_logs_uses_separate_cards_and_stable_filter_grid()
    print("OK")


if __name__ == "__main__":
    main()

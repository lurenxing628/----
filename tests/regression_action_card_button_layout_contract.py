from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _extract_block(source: str, marker: str) -> str:
    start = source.index(marker)
    end = source.find("</div>", start)
    assert end >= 0, f"未找到 {marker} 对应的结束片段"
    return source[start:end]


def test_scheduler_batch_actions_separate_buttons_and_long_notes() -> None:
    for rel_path in ("templates/scheduler/batches.html", "web_new_test/templates/scheduler/batches.html"):
        source = _read(rel_path)
        assert "aps-run-panel" in source
        assert "aps-run-panel-actions" in source
        assert "aps-run-panel-status" in source
        assert "aps-run-panel-help" in source
        actions = _extract_block(source, "aps-run-panel-actions")
        assert "工序的设备、人员、工时必须填写完整" not in actions
        assert "派工方式、智能派工策略、自动分配设备人员" not in actions
        assert "formaction=url_for('scheduler.simulate_schedule')" in source
        assert 'id="jsSelectedCount"' in source


def test_batch_manage_actions_separate_buttons_and_bulk_note() -> None:
    for rel_path in ("templates/scheduler/batches_manage.html", "web_new_test/templates/scheduler/batches_manage.html"):
        source = _read(rel_path)
        assert "aps-action-card" in source
        assert "aps-action-card-actions" in source
        assert "aps-action-card-status" in source
        assert "aps-action-card-note" in source
        actions = _extract_block(source, "aps-action-card-actions")
        assert "留空字段不会覆盖原数据" not in actions
        for field_name in ("bulk_priority", "bulk_due_date", "bulk_remark", "batch_ids"):
            assert field_name in source
        assert "formaction=url_for('scheduler.bulk_copy_batches')" in source
        assert "formaction=url_for('scheduler.bulk_delete_batches')" in source


def test_excel_action_cards_use_dedicated_button_container() -> None:
    source = _read("templates/components/excel_action_cards.html")
    assert "aps-action-card-actions" in source
    assert "aps-excel-card-actions" in source
    assert "action-bar-flat" not in source
    assert "url_for(action.endpoint)" in source


def test_help_details_keep_long_copy_out_of_primary_grid() -> None:
    checks = (
        ("templates/scheduler/batches.html", "查看“发现参数问题就停止排产”的说明"),
        ("templates/scheduler/batches_manage.html", "查看生成工序规则"),
        ("templates/process/list.html", "查看生成工序规则"),
        ("templates/process/detail.html", "查看生成工序规则"),
        ("templates/components/excel_import.html", "查看检查规则"),
        ("templates/scheduler/excel_import_batches.html", "查看检查规则"),
    )
    for rel_path, summary_text in checks:
        source = _read(rel_path)
        assert "aps-help-details" in source or "ui.help_details" in source, rel_path
        assert summary_text in source, rel_path

    macro_source = _read("templates/components/ui_macros.html")
    assert "macro help_details" in macro_source
    assert "macro flash_details" in macro_source
    assert "<details class=\"aps-help-details" in macro_source
    assert "<details class=\"aps-flash-details" in macro_source


def test_dark_theme_covers_summary_and_details_contracts() -> None:
    css = _read("static/css/ui_contract.css")
    for token in (
        'html[data-theme="dark"] .aps-summary-status-line',
        'html[data-theme="dark"] .aps-latest-schedule-head-item',
        'html[data-theme="dark"] .aps-latest-schedule-meta-item',
        'html[data-theme="dark"] .aps-help-details-body',
        'html[data-theme="dark"] .aps-flash-details-body',
        'html[data-theme="dark"] .aps-latest-schedule-head-item--result',
    ):
        assert token in css


def main() -> None:
    test_scheduler_batch_actions_separate_buttons_and_long_notes()
    test_batch_manage_actions_separate_buttons_and_bulk_note()
    test_excel_action_cards_use_dedicated_button_container()
    test_help_details_keep_long_copy_out_of_primary_grid()
    test_dark_theme_covers_summary_and_details_contracts()
    print("OK")


if __name__ == "__main__":
    main()

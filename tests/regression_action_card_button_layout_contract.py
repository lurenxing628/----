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
        assert "aps-action-card-status" in source
        assert "aps-action-card-note" in source
        actions = _extract_block(source, "aps-run-panel-actions")
        assert "工序的设备、人员、工时必须填写完整" not in actions
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


def main() -> None:
    test_scheduler_batch_actions_separate_buttons_and_long_notes()
    test_batch_manage_actions_separate_buttons_and_bulk_note()
    test_excel_action_cards_use_dedicated_button_container()
    print("OK")


if __name__ == "__main__":
    main()

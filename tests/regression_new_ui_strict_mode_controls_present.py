from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_new_ui_strict_mode_controls_present() -> None:
    for rel_path in (
        "templates/scheduler/batches.html",
        "web_new_test/templates/scheduler/batches.html",
    ):
        batches_tpl = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        assert '{% include "scheduler/_run_panel.html" %}' in batches_tpl
    run_panel_tpl = (REPO_ROOT / "templates/scheduler/_run_panel.html").read_text(encoding="utf-8")
    assert "run_options" in run_panel_tpl
    assert "ui.toggle(option.toggle" in run_panel_tpl

    for rel_path in (
        "templates/scheduler/batches_manage.html",
        "web_new_test/templates/scheduler/batches_manage.html",
    ):
        manage_tpl = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        assert "ui.toggle(batch_manage_strict_toggle" in manage_tpl
    toggle_helper = (REPO_ROOT / "web/viewmodels/strict_mode_toggles.py").read_text(encoding="utf-8")
    assert "资料不完整就停下" in toggle_helper

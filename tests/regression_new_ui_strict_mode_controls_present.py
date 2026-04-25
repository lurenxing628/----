from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_new_ui_strict_mode_controls_present() -> None:
    for rel_path in (
        "templates/scheduler/batches.html",
        "web_new_test/templates/scheduler/batches.html",
    ):
        batches_tpl = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        assert 'name="strict_mode"' in batches_tpl
        assert "严格校验排产参数" in batches_tpl

    for rel_path in (
        "templates/scheduler/batches_manage.html",
        "web_new_test/templates/scheduler/batches_manage.html",
    ):
        manage_tpl = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        assert 'name="strict_mode"' in manage_tpl
        assert "严格校验工艺路线" in manage_tpl

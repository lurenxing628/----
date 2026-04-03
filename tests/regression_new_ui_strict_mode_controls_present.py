from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_new_ui_strict_mode_controls_present() -> None:
    batches_tpl = (REPO_ROOT / "web_new_test" / "templates" / "scheduler" / "batches.html").read_text(encoding="utf-8")
    assert 'name="strict_mode"' in batches_tpl
    assert "严格调度参数校验" in batches_tpl

    manage_tpl = (REPO_ROOT / "web_new_test" / "templates" / "scheduler" / "batches_manage.html").read_text(
        encoding="utf-8"
    )
    assert 'name="strict_mode"' in manage_tpl
    assert "严格模式" in manage_tpl

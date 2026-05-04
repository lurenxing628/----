from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_scheduler_config_separates_preset_actions_from_runtime_state() -> None:
    for rel_path in ("templates/scheduler/config.html", "web_new_test/templates/scheduler/config.html"):
        source = _read(rel_path)

        assert "aps-settings-action-grid" in source
        assert "aps-danger-zone" in source
        assert "当前配置状态" in source
        assert source.index("常用方案") < source.index("当前配置状态") < source.index("排产策略配置")

        assert 'name="preset_name"' in source
        assert 'name="next"' in source
        assert 'data-auto-submit="1"' in source
        assert 'data-autosave="true"' in source
        assert 'data-autosave-key="scheduler-config-main"' in source

        assert 'name="ready_weight"' not in source
        assert 'name="auto_assign_persist"' not in source


def main() -> None:
    test_scheduler_config_separates_preset_actions_from_runtime_state()
    print("OK")


if __name__ == "__main__":
    main()

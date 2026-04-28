from __future__ import annotations

from pathlib import Path

from core.plugins.manager import PluginManager
from core.services.common.excel_backend_factory import get_excel_backend
from web.bootstrap.plugins import _apply_enabled_sources

REPO_ROOT = Path(__file__).resolve().parents[1]


def _status_by_id(plugin_status: dict, plugin_id: str) -> dict:
    statuses = list(plugin_status.get("statuses") or [])
    for row in statuses:
        if str(row.get("plugin_id") or "") == plugin_id:
            return dict(row)
    raise AssertionError(f"未找到插件状态：{plugin_id}，当前状态={statuses!r}")


def test_real_optional_plugins_stay_disabled_without_config_and_openpyxl_remains_default() -> None:
    plugin_status = PluginManager.load_from_base_dir(str(REPO_ROOT), logger=None)

    pandas_row = _status_by_id(plugin_status, "pandas_excel_backend")
    ortools_row = _status_by_id(plugin_status, "ortools_probe")
    registry = dict(plugin_status.get("registry") or {})
    capabilities = list(registry.get("capabilities") or [])

    assert pandas_row.get("enabled") == "no", pandas_row
    assert pandas_row.get("loaded") == "no", pandas_row
    assert pandas_row.get("enabled_source") == "default", pandas_row
    assert ortools_row.get("enabled") == "no", ortools_row
    assert ortools_row.get("loaded") == "no", ortools_row
    assert ortools_row.get("enabled_source") == "default", ortools_row
    assert "excel_backend.pandas" not in capabilities
    assert "dependency.ortools" not in capabilities
    assert get_excel_backend().__class__.__name__ == "OpenpyxlBackend"


def test_apply_enabled_sources_keeps_explicit_config_source_and_public_error_message() -> None:
    plugin_status = _apply_enabled_sources(
        {
            "statuses": [
                {
                    "plugin_id": "pandas_excel_backend",
                    "enabled": "yes",
                    "loaded": "no",
                    "enabled_source": "default",
                    "error": "SECRET_INTERNAL_TRACE",
                },
                {
                    "plugin_id": "ortools_probe",
                    "enabled": "no",
                    "loaded": "no",
                    "enabled_source": "default",
                },
            ]
        },
        enabled_source_map={"pandas_excel_backend": "config"},
        default_source="default",
    )

    pandas_row = _status_by_id(plugin_status, "pandas_excel_backend")
    ortools_row = _status_by_id(plugin_status, "ortools_probe")

    assert pandas_row.get("enabled_source") == "config", pandas_row
    assert pandas_row.get("error") == "插件加载失败，请查看系统日志。", pandas_row
    assert ortools_row.get("enabled_source") == "default", ortools_row
    assert plugin_status.get("config_source") == "mixed", plugin_status
    assert "SECRET_INTERNAL_TRACE" not in str(plugin_status)


def test_apply_enabled_sources_summarizes_default_due_to_config_read_failed() -> None:
    plugin_status = _apply_enabled_sources(
        {
            "statuses": [
                {"plugin_id": "demo_a", "enabled": "yes", "loaded": "yes", "enabled_source": "default"},
                {"plugin_id": "demo_b", "enabled": "yes", "loaded": "yes", "enabled_source": "default"},
            ]
        },
        enabled_source_map={
            "demo_a": "default_due_to_config_read_failed",
            "demo_b": "default_due_to_config_read_failed",
        },
        default_source="default",
    )

    assert plugin_status.get("config_source") == "default_due_to_config_read_failed", plugin_status


def test_system_backup_template_mentions_plugin_conflicts_and_telemetry_state() -> None:
    template_text = (REPO_ROOT / "templates" / "system" / "backup.html").read_text(encoding="utf-8")
    assert "冲突能力" in template_text
    assert "留痕状态" in template_text
    assert "telemetry_persisted" in template_text
    assert "conflicted_capabilities" in template_text

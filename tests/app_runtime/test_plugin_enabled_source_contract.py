"""回归测试：可选插件启用来源(enabled_source)契约——无配置时 pandas_excel_backend/ortools_probe 保持 enabled=no、source=default 且默认 Excel 后端仍为 OpenpyxlBackend、能力表不含 pandas/ortools；
_apply_enabled_sources 保留显式 config 来源、把插件加载错误脱敏为「请联系维护人员」公开文案（不泄露内部堆栈）、config_source 汇总 mixed/default_due_to_config_read_failed；并校验备份页模板/presenter 暴露冲突能力与留痕状态字段。"""

from __future__ import annotations

from pathlib import Path

from core.plugins.manager import PluginManager
from core.services.common.excel_backend_factory import get_excel_backend
from tests._support.paths import REPO_ROOT
from web.bootstrap.plugins import _apply_enabled_sources


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
    assert pandas_row.get("error") == "插件加载失败，请联系维护人员检查系统运行记录。", pandas_row
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

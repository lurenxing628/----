"""Plugin normalization uses the existing low-level policy without service imports."""

from __future__ import annotations

from typing import Optional, get_type_hints

import pytest

from core import plugins
from core.plugins import manager
from core.services.common.enum_normalizers import normalize_yes_no_wide as service_normalize
from tests._support.dependency_boundaries import assert_import_orders, assert_no_import_prefixes
from tests._support.paths import REPO_ROOT


@pytest.mark.parametrize("default", ("yes", "no", "ON", "off", "garbage", "", None))
def test_plugin_normalization_matches_existing_service_policy(default):
    for raw in (None, "", "yes", "YES", " y ", "no", "on", "off", True, False, 1, 0, "是", "否", "Maybe", "2"):
        assert manager._normalize_yes_no(raw, default=default) == service_normalize(raw, default=default, unknown_policy="default")


def test_public_plugin_objects_and_state_ownership_are_unchanged(monkeypatch):
    names = ("PluginManager", "get_plugin_registry", "get_plugin_status", "reset_plugin_state")
    for name in names:
        assert getattr(plugins, name) is getattr(manager, name)
    assert_import_orders("core.plugins", "core.plugins.manager", names)
    calls = []
    monkeypatch.setattr(manager, "normalize_yes_no_wide", lambda value, **kwargs: calls.append((value, kwargs)) or "yes")
    assert manager._normalize_yes_no("custom", default="no") == "yes"
    assert calls == [("custom", {"default": "no", "unknown_policy": "default"})]


def test_plugin_manager_has_no_service_layer_imports():
    assert_no_import_prefixes(REPO_ROOT / "core/plugins/manager.py", ("core.services",))


def test_public_reset_annotation_is_resolvable_on_python38():
    assert get_type_hints(manager.reset_plugin_state)["base_dir"] == Optional[str]

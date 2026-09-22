"""Config save policy signatures remain resolvable on the Python 3.8 runtime."""

from __future__ import annotations

from typing import Set, get_type_hints

from core.services.scheduler.config.config_page_save_policy import ConfigPageSavePolicy


def test_page_save_policy_annotations_resolve_on_python38() -> None:
    assert get_type_hints(ConfigPageSavePolicy.submitted_fields)["return"] == Set[str]
    assert get_type_hints(ConfigPageSavePolicy.write_values)["submitted_fields"] == Set[str]

from __future__ import annotations

from pathlib import Path


def test_route_normalizers_no_longer_own_version_parser_logic() -> None:
    source = Path("web/routes/normalizers.py").read_text(encoding="utf-8")

    assert "def default_version_to_latest" not in source
    assert "def parse_explicit_version_or_latest" not in source
    assert "def normalize_version_or_latest_fallback" not in source
    assert "def normalize_version_or_latest(" not in source
    assert "def resolve_route_version_or_latest" not in source


def test_resource_dispatch_service_no_longer_keeps_idle_version_parser() -> None:
    source = Path("core/services/scheduler/resource_dispatch_service.py").read_text(encoding="utf-8")

    assert "_normalize_strict_positive_version" not in source
    assert "resolve_version_or_latest" in source

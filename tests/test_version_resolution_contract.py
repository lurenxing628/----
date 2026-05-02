from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.version_resolution import resolve_version_or_latest


def test_version_resolution_defaults_to_latest() -> None:
    result = resolve_version_or_latest(None, latest_version=7)

    assert result.has_history is True
    assert result.selected_version == 7
    assert result.requested_version is None
    assert result.status == "ok"
    assert result.source == "default"


def test_version_resolution_accepts_latest_keyword() -> None:
    result = resolve_version_or_latest("latest", latest_version=9)

    assert result.selected_version == 9
    assert result.status == "ok"
    assert result.source == "latest"


def test_version_resolution_reports_no_history_without_fallback_version() -> None:
    result = resolve_version_or_latest(None, latest_version=0)

    assert result.has_history is False
    assert result.selected_version is None
    assert result.status == "no_history"


def test_version_resolution_reports_missing_explicit_history() -> None:
    result = resolve_version_or_latest(
        "5",
        latest_version=9,
        version_exists=lambda version: False,
    )

    assert result.has_history is True
    assert result.selected_version is None
    assert result.requested_version == 5
    assert result.status == "missing_history"


def test_version_resolution_rejects_invalid_explicit_value() -> None:
    with pytest.raises(ValidationError):
        resolve_version_or_latest("bad", latest_version=9)

    with pytest.raises(ValidationError):
        resolve_version_or_latest("0", latest_version=9)

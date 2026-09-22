"""Fallback pages keep theme selection and secondary-copy contrast truthful."""

import re

import pytest

from tests._support.paths import REPO_ROOT

TEMPLATES = (
    "templates/workbench/legacy_style.html",
    "templates/workbench/recovery.html",
    "templates/workbench/unavailable.html",
)
THEME_PAGES = (
    "templates/workbench/legacy_base.html",
    "templates/workbench/recovery.html",
    "templates/workbench/unavailable.html",
)


def _read(path):
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _luminance(value):
    channels = [int(value[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
              for channel in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(left, right):
    darker, lighter = sorted((_luminance(left), _luminance(right)))
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("path", TEMPLATES)
def test_fallback_light_muted_text_meets_normal_text_contrast(path):
    source = _read(path)
    light = source.split("data-theme=\"dark\"", 1)[0]
    page = re.search(r"--page\s*:\s*#([0-9a-fA-F]{6})", light).group(1)
    surface = re.search(r"--surface\s*:\s*#([0-9a-fA-F]{6})", light).group(1)
    muted = re.search(r"--muted\s*:\s*#([0-9a-fA-F]{6})", light).group(1)
    assert _contrast(muted, page) >= 4.5, path
    assert _contrast(muted, surface) >= 4.5, path


@pytest.mark.parametrize("path", THEME_PAGES)
def test_fallback_theme_uses_valid_secondary_value_when_primary_is_invalid(path):
    compact = re.sub(r"\s+", "", _read(path))
    assert (
        "preferred==='dark'||preferred==='light'?preferred:"
        "legacy==='dark'||legacy==='light'?legacy:null"
    ) in compact, path


def test_storage_failure_messages_match_the_theme_that_remains_visible():
    for path in ("templates/workbench/legacy_base.html", "templates/workbench/unavailable.html"):
        assert "本页沿用打开时的主题" in _read(path), path
    recovery = _read("templates/workbench/recovery.html")
    assert "document.documentElement.dataset.theme='light'" in recovery
    assert "本页按浅色显示" in recovery

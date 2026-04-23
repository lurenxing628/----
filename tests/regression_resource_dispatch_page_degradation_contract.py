from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_resource_dispatch_page_renders_generic_degradation_channel() -> None:
    template_source = _read("templates/scheduler/resource_dispatch.html")
    js_source = _read("static/js/resource_dispatch.js")

    assert 'id="rdDegradationSummary"' in template_source
    assert "summary.degradation_events" in js_source
    assert "rdDegradationSummary" in js_source

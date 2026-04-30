from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_resource_dispatch_core_layers_do_not_import_web() -> None:
    for directory in ("core", "data"):
        for path in (REPO_ROOT / directory).rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "from web" not in source
            assert "import web" not in source


def test_resource_dispatch_service_no_longer_owns_filter_label_helpers() -> None:
    source = _read("core/services/scheduler/resource_dispatch_service.py")

    assert "_period_preset_label" not in source
    assert "_scope_type_label" not in source
    assert "_team_axis_label" not in source
    assert "def build_export" not in source
    assert "resource_dispatch_excel" not in source


def test_resource_dispatch_support_filters_stay_raw() -> None:
    source = _read("core/services/scheduler/resource_dispatch_support.py")

    assert "scope_type_label:" not in source
    assert "team_axis_label:" not in source
    assert "period_preset_label" not in source
    assert "\"scope_label\"" not in source


def test_resource_dispatch_rows_leave_display_labels_to_viewmodel() -> None:
    source = _read("core/services/scheduler/resource_dispatch_rows.py")

    assert "display_machine" not in source
    assert "display_operator" not in source
    assert "\"current_resource_label\"" not in source
    assert "\"counterpart_resource_label\"" not in source
    assert "\"team_relation_label\"" not in source

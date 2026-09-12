"""Maintained CSS publication fails closed before changing existing assets."""

import importlib.util
import json
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "scripts/workbench"
STYLE_ROOT = "frontend/workbench/app/styles"


@pytest.fixture
def builder(monkeypatch):
    monkeypatch.syspath_prepend(str(TOOLS))
    spec = importlib.util.spec_from_file_location("workbench_style_build", TOOLS / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def order(tmp_path):
    styles = tmp_path / STYLE_ROOT
    styles.mkdir(parents=True)
    (styles / "20-controls.css").write_text(".control { color: red; }\n", encoding="utf-8")
    (styles / "00-tokens.css").write_text(":root { --text: black; }\n", encoding="utf-8")
    return {"styles": ["20-controls.css", "00-tokens.css"]}


def test_css_uses_declared_cascade_order_without_writing_files(builder, tmp_path, order):
    actual = builder.live_style_inputs(tmp_path, order)
    assert [row["path"] for row in actual] == ["app/styles/" + name for name in order["styles"]]
    assert all(row["data"] == (tmp_path / "frontend/workbench" / row["path"]).read_bytes() for row in actual)
    assert not (tmp_path / "static").exists()


@pytest.mark.parametrize("names", (
    None, "00-tokens.css", True, [None], [[]], [True], [1], [""], [".css"],
    ["../00-tokens.css"], ["nested/00-tokens.css"], ["nested\\00-tokens.css"],
    ["/00-tokens.css"], ["./00-tokens.css"], ["style.css?query.css"],
    ["style.css#fragment.css"], ["style%2Ffile.css"], ["style.CSS"],
    ["style.js"], ["style.css\n"], ["00-tokens.css", "00-tokens.css"],
))
def test_css_order_rejects_invalid_or_duplicate_names(builder, tmp_path, names):
    with pytest.raises(ValueError, match="explicit unique CSS filenames"):
        builder.live_style_inputs(tmp_path, {"styles": names})


def test_css_requires_an_explicit_list_even_when_folder_is_absent(builder, tmp_path):
    with pytest.raises(ValueError, match="explicit unique CSS filenames"):
        builder.live_style_inputs(tmp_path, {})
    assert builder.live_style_inputs(tmp_path, {"styles": []}) == []


@pytest.mark.parametrize("name", ("00-tokens.css", "20-controls.css"))
def test_declared_css_cannot_be_missing(builder, tmp_path, order, name):
    (tmp_path / STYLE_ROOT / name).unlink()
    with pytest.raises(ValueError, match="Live styles not ready; missing=" + name):
        builder.live_style_inputs(tmp_path, order)


@pytest.mark.parametrize("name", ("unlisted.css", "nested/unlisted.css", "UPPER.CSS"))
def test_unlisted_css_is_never_silently_published(builder, tmp_path, order, name):
    file = tmp_path / STYLE_ROOT / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(".unlisted {}", encoding="utf-8")
    with pytest.raises(ValueError, match="unlisted=" + name):
        builder.live_style_inputs(tmp_path, order)


def test_style_symlink_cannot_read_a_file_outside_style_sources(builder, tmp_path):
    outside = tmp_path / "outside.css"
    outside.write_text(".outside {}", encoding="utf-8")
    styles = tmp_path / STYLE_ROOT
    styles.mkdir(parents=True)
    (styles / "escaped.css").symlink_to(outside)
    with pytest.raises(ValueError):
        builder.live_style_inputs(tmp_path, {"styles": ["escaped.css"]})


@pytest.mark.parametrize("change", ("content", "add", "remove", "order"))
def test_css_change_during_compile_preserves_published_payload(builder, tmp_path, order, monkeypatch, change):
    """Use a compiler stub so the race is deterministic, then check the real publisher."""
    app = tmp_path / "frontend/workbench/app"
    for name in ("theme.js", "main.jsx"):
        (app / name).write_text("// fixture\n", encoding="utf-8")
    order.update({"theme": "theme.js", "live": ["main.jsx"], "never_live": [],
                  "foundation": [], "bootstrap": "", "entry": "style-test"})
    prototype = tmp_path / "frontend/workbench/prototype"
    notice = prototype / "ui_kits/workbench/assets/lucide-LICENSE"
    notice.parent.mkdir(parents=True)
    notice.write_text("fixture", encoding="utf-8")
    snapshot = {"files": [], "entries": {"index": {"icons": ["icon.svg"]}}}
    vendor = tmp_path / "frontend/workbench/vendor"
    vendor.mkdir()
    (vendor / "vendor-manifest.json").write_text(json.dumps({"files": [], "scripts": [],
        "packages": [{"name": name, "version": "18.3.1"} for name in ("react", "react-dom")]}), encoding="utf-8")
    tool_copy = tmp_path / "tools"
    tool_copy.mkdir()
    for name in ("build.py", "asset_sources.py", "build-order.json", "compile.cjs", "ds-projection.cjs"):
        (tool_copy / name).write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(builder, "TOOLS", tool_copy)
    monkeypatch.setattr(builder, "read_inputs", lambda root: (prototype, snapshot, set(), order))
    monkeypatch.setattr(builder, "verify_snapshot", lambda *args: set())
    monkeypatch.setattr(builder, "style_assets", lambda *args: ({}, []))
    monkeypatch.setattr(builder, "asset_records", lambda *args: [])

    def compile_and_change(node, prototype, order, sources, combined=False):
        source = app / "styles/00-tokens.css"
        if change == "content":
            source.write_text(".changed {}", encoding="utf-8")
        elif change == "add":
            (app / "styles/late.css").write_text(".late {}", encoding="utf-8")
        elif change == "remove":
            source.unlink()
        else:
            (tool_copy / "build-order.json").write_text("changed", encoding="utf-8")
        return sources

    monkeypatch.setattr(builder, "compile_sources", compile_and_change)
    output = tmp_path / "static/workbench"
    output.mkdir(parents=True)
    (output / "asset-manifest.json").write_bytes(b"existing manifest")
    (output / "published.css").write_bytes(b"existing CSS")
    before = {path: path.read_bytes() for path in output.iterdir()}
    with pytest.raises(ValueError, match="changed during compilation|Live styles not ready"):
        builder.build(tmp_path, output, "unused-node")
    assert before == {path: path.read_bytes() for path in output.iterdir()}

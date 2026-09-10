"""Explicit live/pending source boundaries without compilation or publication."""

import copy
import importlib.util
import re
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "scripts/workbench"
APP = Path("frontend/workbench/app")
LIVE_INPUTS = [
    {"path": "app/theme.js", "code": "window.theme = 'light';\n"},
    {"path": "app/z-last.js", "code": "window.sourceOrder = ['z'];\n"},
    {"path": "app/a-first.jsx", "code": "window.sourceOrder.push('a');\n"},
]


@pytest.fixture
def builder(monkeypatch):
    monkeypatch.syspath_prepend(str(TOOLS))
    spec = importlib.util.spec_from_file_location("workbench_pending_build", TOOLS / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def order(tmp_path):
    app = tmp_path / APP
    app.mkdir(parents=True)
    for source in LIVE_INPUTS:
        (app / Path(source["path"]).name).write_text(source["code"], encoding="utf-8")
    return {"theme": "theme.js", "live": ["z-last.js", "a-first.jsx"]}


@pytest.mark.parametrize("explicit_empty", (False, True), ids=("omitted", "empty"))
def test_pending_is_optional_and_live_order_is_preserved(builder, tmp_path, order, explicit_empty):
    if explicit_empty:
        order["pending_live"] = []
    before = copy.deepcopy(order)
    assert builder.live_inputs(tmp_path, order) == LIVE_INPUTS
    assert order == before


def test_pending_scripts_are_not_read_or_returned(builder, tmp_path, order):
    order["pending_live"] = ["Draft.jsx", "draft-contract.js"]
    for name in order["pending_live"]:
        (tmp_path / APP / name).write_bytes(b"\xff unfinished source")
    before = copy.deepcopy(order)
    assert builder.live_inputs(tmp_path, order) == LIVE_INPUTS
    assert order == before
    for name in order["pending_live"]:
        assert (tmp_path / APP / name).read_bytes() == b"\xff unfinished source"
    assert not (tmp_path / "static").exists()


def test_pending_names_may_be_declared_before_files_exist(builder, tmp_path, order):
    order["pending_live"] = ["Future.jsx", "future-contract.js"]
    assert all(not (tmp_path / APP / name).exists() for name in order["pending_live"])
    assert builder.live_inputs(tmp_path, order) == LIVE_INPUTS


@pytest.mark.parametrize("pending", (None, [], ["Draft.jsx"]), ids=("omitted", "empty", "declared"))
@pytest.mark.parametrize("name", ("unknown.js", "Unknown.jsx"))
def test_unknown_scripts_still_fail_closed(builder, tmp_path, order, pending, name):
    if pending is not None:
        order["pending_live"] = pending
        for declared in pending:
            (tmp_path / APP / declared).write_text("unfinished", encoding="utf-8")
    (tmp_path / APP / name).write_text("window.unknown = true;", encoding="utf-8")
    with pytest.raises(ValueError, match="unlisted=" + re.escape(name)):
        builder.live_inputs(tmp_path, order)


@pytest.mark.parametrize("name", ("theme.js", "z-last.js", "a-first.jsx"))
def test_pending_does_not_make_missing_live_sources_optional(builder, tmp_path, order, name):
    order["pending_live"] = ["Draft.jsx"]
    (tmp_path / APP / "Draft.jsx").write_text("unfinished", encoding="utf-8")
    (tmp_path / APP / name).unlink()
    with pytest.raises(ValueError, match="missing=" + re.escape(name)):
        builder.live_inputs(tmp_path, order)


@pytest.mark.parametrize("name", ("theme.js", "z-last.js", "a-first.jsx"))
def test_live_and_pending_sources_cannot_overlap(builder, tmp_path, order, name):
    order["pending_live"] = [name]
    with pytest.raises(ValueError, match="Pending live sources"):
        builder.live_inputs(tmp_path, order)


@pytest.mark.parametrize("name", ("Draft.jsx", "draft-contract.js"))
def test_duplicate_pending_sources_are_rejected_even_when_absent(builder, tmp_path, order, name):
    order["pending_live"] = [name, name]
    with pytest.raises(ValueError, match="Pending live sources"):
        builder.live_inputs(tmp_path, order)


@pytest.mark.parametrize("name", ("theme.js", "z-last.js", "a-first.jsx"))
def test_duplicate_live_sources_and_theme_overlap_remain_rejected(builder, tmp_path, order, name):
    order["pending_live"] = ["Draft.jsx"]
    order["live"].append(name)
    with pytest.raises(ValueError, match="Duplicate live source"):
        builder.live_inputs(tmp_path, order)


@pytest.mark.parametrize("pending", (None, True, 1, "Draft.jsx", ("Draft.jsx",), {"Draft.jsx": True}))
def test_pending_must_be_a_list(builder, tmp_path, order, pending):
    order["pending_live"] = pending
    with pytest.raises(ValueError, match="Pending live sources"):
        builder.live_inputs(tmp_path, order)


@pytest.mark.parametrize("name", (
    None, True, 1, [], {}, "", ".", "..", ".js",
    "../draft.js", "..\\draft.js", "nested/draft.jsx", "nested\\draft.jsx",
    "./draft.js", "/tmp/draft.js", "C:\\temp\\draft.jsx", "C:/temp/draft.jsx",
    "draft.js/", "draft.txt", "draft.css", "draft.js.map", "draft.JS", "draft.JSX",
))
def test_pending_requires_bare_script_names(builder, tmp_path, order, name):
    order["pending_live"] = [name]
    with pytest.raises(ValueError, match="Pending live sources"):
        builder.live_inputs(tmp_path, order)


def test_pending_source_requires_explicit_promotion_to_live(builder, tmp_path, order):
    code = "window.draft = true;\n"
    (tmp_path / APP / "Draft.jsx").write_text(code, encoding="utf-8")
    order["pending_live"] = ["Draft.jsx"]
    assert builder.live_inputs(tmp_path, order) == LIVE_INPUTS
    order["pending_live"] = []
    with pytest.raises(ValueError, match="unlisted=Draft\\.jsx"):
        builder.live_inputs(tmp_path, order)
    order["live"].append("Draft.jsx")
    assert builder.live_inputs(tmp_path, order) == LIVE_INPUTS + [{"path": "app/Draft.jsx", "code": code}]

"""契约测试：symbol-locator 静态查询、Jedi 降级、SCIP 深度查询和门禁登记边界。"""

from __future__ import annotations

import json
import subprocess
import sys

from tools.symbol_locator import cli, freshness, render, scip_deep, static_index


def _sample_index():
    functions = {
        "a.py::foo": {"rel": "a.py", "line": 1, "end": 5, "cls": None, "name": "foo", "fan_in": 1, "fan_out": 1},
        "a.py::caller": {"rel": "a.py", "line": 8, "end": 9, "cls": None, "name": "caller", "fan_in": 0, "fan_out": 1},
        "a.py::callee": {"rel": "a.py", "line": 11, "end": 12, "cls": None, "name": "callee", "fan_in": 1, "fan_out": 0},
        "b.py::One.to_dict": {"rel": "b.py", "line": 3, "end": 4, "cls": "One", "name": "to_dict", "fan_in": 0, "fan_out": 0},
        "c.py::Two.to_dict": {"rel": "c.py", "line": 6, "end": 7, "cls": "Two", "name": "to_dict", "fan_in": 0, "fan_out": 0},
    }
    edges = [
        {"from": "a.py::caller", "to": "a.py::foo", "kind": "call", "ambiguous": False},
        {"from": "a.py::foo", "to": "a.py::callee", "kind": "call", "ambiguous": False},
        {"from": "x.py::maybe", "to": "a.py::foo", "kind": "call", "ambiguous": True},
        {"from": "a.py::foo", "to": "x.py::maybe", "kind": "call", "ambiguous": True},
    ]
    dynamic = [{"func": "a.py::foo", "rel": "a.py", "line": 1, "hints": ["getattr"]}]
    return static_index.StaticIndex(functions, edges, dynamic=dynamic)


def _scip_symbol(path, name):
    return f"scip-python python aps version `{path.replace('/', '.')}`/{name}()."


def test_static_whereis_unique_and_collision_menu(capsys):
    index = _sample_index()

    assert render.render_whereis("foo", index) == 0
    out = capsys.readouterr().out
    assert "a.py:1-5" in out
    assert "被调 1" in out

    assert render.render_whereis("to_dict", index) == 0
    out = capsys.readouterr().out
    assert "2 处同名" in out
    assert "One.to_dict" in out
    assert "Two.to_dict" in out


def test_relation_outputs_confident_edges_and_blindspots(capsys):
    index = _sample_index()

    assert render.render_relation("foo", index, "callers") == 0
    callers = capsys.readouterr().out
    assert "全量 confident 边 1 条" in callers
    assert "a.py:8" in callers
    assert "另有 1 条 ambiguous 边" in callers
    assert "未含 tests/" in callers

    assert render.render_relation("foo", index, "callees") == 0
    callees = capsys.readouterr().out
    assert "a.py:11" in callees
    assert "动态调用" in callees


def test_json_and_not_found_contract(capsys):
    index = _sample_index()

    assert render.render_relation("foo", index, "callers", as_json=True) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["symbol"] == "foo"
    assert payload["result"]["a.py::foo"]["related"] == ["a.py::caller"]

    assert render.render_whereis("fooo", index, as_json=True) == 1
    missing = json.loads(capsys.readouterr().out)
    assert missing["error"] == "not_found"
    assert "foo" in missing["suggestions"]


def test_jedi_unavailable_degrades_to_static_menu(monkeypatch, capsys):
    index = _sample_index()

    from tools.symbol_locator import jedi_resolver

    monkeypatch.setattr(jedi_resolver, "resolve_at", lambda _file, _line, _symbol: None)
    monkeypatch.setattr(jedi_resolver, "available", lambda: False)

    assert render.render_whereis("to_dict", index, at=("a.py", 1)) == 0
    out = capsys.readouterr().out
    assert "jedi 不可用" in out
    assert "2 处同名" in out


def test_whereis_at_success_uses_jedi_hit(monkeypatch, capsys):
    index = _sample_index()

    from tools.symbol_locator import jedi_resolver

    monkeypatch.setattr(
        jedi_resolver,
        "resolve_at",
        lambda _file, _line, _symbol: [("core/models/calendar.py", 58, "core.models.calendar.WorkCalendar.to_dict")],
    )
    monkeypatch.setattr(jedi_resolver, "available", lambda: True)

    assert render.render_whereis("to_dict", index, as_json=True, at=("core/services/scheduler/calendar_admin.py", 306)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["resolved"] == [
        {"rel": "core/models/calendar.py", "line": 58, "full_name": "core.models.calendar.WorkCalendar.to_dict"}
    ]


def test_cli_parses_whereis_at(monkeypatch):
    seen = {}

    monkeypatch.setattr(cli, "_ensure_fresh", lambda force, as_json: None)
    monkeypatch.setattr(static_index, "load", lambda: _sample_index())

    def fake_render(symbol, index, as_json=False, at=None):
        seen.update({"symbol": symbol, "as_json": as_json, "at": at})
        return 0

    monkeypatch.setattr(render, "render_whereis", fake_render)

    assert cli.main(["whereis", "to_dict", "--at", "a.py:1", "--json"]) == 0
    assert seen == {"symbol": "to_dict", "as_json": True, "at": ("a.py", 1)}


def test_cli_rejects_invalid_whereis_at(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_ensure_fresh", lambda force, as_json: None)

    assert cli.main(["whereis", "foo", "--at", "bad-format", "--json"]) == 2
    err = capsys.readouterr().err
    assert "--at 需要 FILE:LINE" in err

    assert cli.main(["whereis", "foo", "--at", "a.py:0", "--json"]) == 2
    err = capsys.readouterr().err
    assert "LINE 必须是大于 0" in err


def test_whereis_at_json_degradation_stays_json(monkeypatch, capsys):
    index = _sample_index()

    from tools.symbol_locator import jedi_resolver

    monkeypatch.setattr(jedi_resolver, "resolve_at", lambda _file, _line, _symbol: None)
    monkeypatch.setattr(jedi_resolver, "available", lambda: False)

    assert render.render_whereis("to_dict", index, as_json=True, at=("a.py", 1)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["degraded"] is True
    assert payload["reason"] == "missing_jedi"
    assert len(payload["matches"]) == 2


def test_deep_query_uses_scip_zero_based_ranges_and_tests(monkeypatch):
    index = _sample_index()
    foo_symbol = _scip_symbol("a.py", "foo")
    bar_symbol = _scip_symbol("b.py", "bar")
    docs = [
        {
            "relative_path": "a.py",
            "occurrences": [
                {"range": [0, 4, 7], "symbol": foo_symbol, "symbol_roles": 1, "enclosing_range": [0, 0, 4, 20]},
                {"range": [1, 8, 11], "symbol": bar_symbol, "symbol_roles": 8},
                {"range": [8, 8, 11], "symbol": bar_symbol, "symbol_roles": 8},
            ],
        },
        {
            "relative_path": "tests/test_a.py",
            "occurrences": [
                {"range": [9, 2, 5], "symbol": foo_symbol, "symbol_roles": 8},
            ],
        },
    ]
    monkeypatch.setattr(
        scip_deep,
        "load_documents",
        lambda index_path=None: {"path": "index.scip", "mtime": 1.0, "documents": docs},
    )
    monkeypatch.setattr(scip_deep, "_is_call_occurrence", lambda _doc, _occ, _cache: True)

    callers = scip_deep.query("foo", "callers", index)
    assert callers["definitions"][0]["line"] == 1
    assert callers["rows"] == [
        {
            "path": "tests/test_a.py",
            "line": 10,
            "range": [9, 2, 5],
            "symbol": foo_symbol,
            "display": "a.py/foo()",
            "target_symbol": foo_symbol,
        }
    ]

    callees = scip_deep.query("foo", "callees", index)
    assert [row["line"] for row in callees["rows"]] == [2]
    assert callees["rows"][0]["display"] == "b.py/bar()"


def test_deep_callers_filters_non_call_references(monkeypatch):
    index = static_index.StaticIndex({}, [], dynamic=[])
    foo_symbol = _scip_symbol("sample.py", "foo")
    docs = [
        {
            "relative_path": "sample.py",
            "occurrences": [
                {"range": [0, 4, 7], "symbol": foo_symbol, "symbol_roles": 1, "enclosing_range": [0, 0, 1, 1]},
                {"range": [2, 14, 17], "symbol": foo_symbol, "symbol_roles": 8},
                {"range": [3, 10, 13], "symbol": foo_symbol, "symbol_roles": 8},
                {"range": [4, 10, 13], "symbol": foo_symbol, "symbol_roles": 8},
                {"range": [5, 4, 7], "symbol": foo_symbol, "symbol_roles": 8},
                {"range": [6, 7, 10], "symbol": foo_symbol, "symbol_roles": 8},
            ],
        }
    ]
    source = "\n".join([
        "def foo():",
        "    pass",
        "from sample import foo",
        "callback = foo",
        "def bar(default=foo):",
        "    foo()",
        "    ns.foo()",
    ])
    monkeypatch.setattr(scip_deep, "_read_source", lambda _path: source)
    monkeypatch.setattr(
        scip_deep,
        "load_documents",
        lambda index_path=None: {"path": "index.scip", "mtime": 1.0, "documents": docs},
    )

    callers = scip_deep.query("foo", "callers", index)
    assert [(row["path"], row["line"]) for row in callers["rows"]] == [("sample.py", 6), ("sample.py", 7)]


def test_deep_relation_can_query_test_only_symbols(monkeypatch, capsys):
    index = _sample_index()
    test_symbol = _scip_symbol("tests.test_symbol_locator_contract", "test_only")
    docs = [
        {
            "relative_path": "tests/test_symbol_locator_contract.py",
            "occurrences": [
                {"range": [20, 4, 13], "symbol": test_symbol, "symbol_roles": 1, "enclosing_range": [20, 0, 21, 1]},
                {"range": [40, 10, 19], "symbol": test_symbol, "symbol_roles": 8},
            ],
        }
    ]
    monkeypatch.setattr(
        scip_deep,
        "load_documents",
        lambda index_path=None: {"path": "index.scip", "mtime": 1.0, "documents": docs},
    )
    monkeypatch.setattr(scip_deep, "_is_call_occurrence", lambda _doc, _occ, _cache: True)

    assert render.render_relation("test_only", index, "callers", as_json=True, deep=True) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["definitions"][0]["path"] == "tests/test_symbol_locator_contract.py"
    assert payload["rows"][0]["line"] == 41


def test_deep_missing_scip_returns_structured_degradation(monkeypatch, capsys):
    index = _sample_index()

    monkeypatch.setattr(scip_deep.shutil, "which", lambda name: None if name == "scip" else "/bin/" + name)

    assert render.render_relation("foo", index, "callers", as_json=True, deep=True) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["engine"] == "scip"
    assert payload["error"] == "missing_scip_cli"
    assert "未找到 scip CLI" in payload["message"]


def test_deep_missing_index_returns_structured_degradation(monkeypatch, capsys):
    index = _sample_index()

    monkeypatch.setattr(scip_deep.shutil, "which", lambda name: "/bin/" + name)
    monkeypatch.setattr(scip_deep.os.path, "exists", lambda path: False if path.endswith("index.scip") else True)

    assert render.render_relation("foo", index, "callers", as_json=True, deep=True) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["engine"] == "scip"
    assert payload["error"] == "missing_index"
    assert "scip-python index" in "\n".join(payload["hints"])


def test_cli_parses_deep_without_touching_default_path(monkeypatch):
    seen = {}

    monkeypatch.setattr(cli, "_ensure_fresh", lambda force, as_json: None)
    monkeypatch.setattr(static_index, "load", lambda: _sample_index())

    def fake_render(symbol, index, direction, as_json=False, deep=False):
        seen.update({"symbol": symbol, "direction": direction, "as_json": as_json, "deep": deep})
        return 0

    monkeypatch.setattr(render, "render_relation", fake_render)

    assert cli.main(["callers", "foo", "--deep", "--json"]) == 0
    assert seen == {"symbol": "foo", "direction": "callers", "as_json": True, "deep": True}


def test_freshness_rebuild_failure_keeps_old_snapshot(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(freshness, "is_stale", lambda: True)
    monkeypatch.setattr(freshness, "rebuild", lambda: calls.append("rebuild") or False)
    monkeypatch.setattr(freshness, "snapshot_label", lambda: "old-snapshot")

    cli._ensure_fresh(False, False)
    err = capsys.readouterr().err
    assert calls == ["rebuild"]
    assert "重建失败,沿用旧快照" in err
    assert "[快照 old-snapshot]" in err


def test_freshness_rebuild_success_reports_new_snapshot(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(freshness, "is_stale", lambda: True)
    monkeypatch.setattr(freshness, "rebuild", lambda: calls.append("rebuild") or True)
    monkeypatch.setattr(freshness, "snapshot_label", lambda: "new-snapshot")

    cli._ensure_fresh(False, False)
    err = capsys.readouterr().err
    assert calls == ["rebuild"]
    assert "重建失败" not in err
    assert "[快照 new-snapshot]" in err


def test_freshness_rebuild_refreshes_isolated_snapshot(tmp_path, monkeypatch):
    callgraph_dir = tmp_path / "callgraph"
    extractor = tmp_path / "extractor.py"
    extractor.write_text(
        "\n".join([
            "import json, os",
            "out = os.environ['CHECKUP_CALLGRAPH']",
            "os.makedirs(out, exist_ok=True)",
            "functions = {'tmp.py::fresh_func': {'rel': 'tmp.py', 'line': 7, 'end': 9, 'cls': None, 'name': 'fresh_func', 'fan_in': 0, 'fan_out': 0}}",
            "json.dump(functions, open(os.path.join(out, 'functions.json'), 'w'))",
            "json.dump([], open(os.path.join(out, 'edges.json'), 'w'))",
            "json.dump([], open(os.path.join(out, 'dynamic_unresolved.json'), 'w'))",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setenv("CHECKUP_CALLGRAPH", str(callgraph_dir))
    monkeypatch.setattr(freshness, "_EXTRACT", str(extractor))
    monkeypatch.setattr(freshness, "_VENV_PY", sys.executable)

    assert freshness.rebuild() is True
    index = static_index.load(
        functions_path=str(callgraph_dir / "functions.json"),
        edges_path=str(callgraph_dir / "edges.json"),
        dynamic_path=str(callgraph_dir / "dynamic_unresolved.json"),
    )
    assert index.info("tmp.py::fresh_func")["line"] == 7


def test_freshness_rebuild_networkx_failure_prints_install_hint(monkeypatch, capsys):
    monkeypatch.setattr(freshness, "is_stale", lambda: True)
    monkeypatch.setattr(freshness, "snapshot_label", lambda: "old-snapshot")

    def fake_run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            1,
            "extractor",
            stderr="ModuleNotFoundError: No module named 'networkx'",
        )

    monkeypatch.setattr(freshness.subprocess, "run", fake_run)

    cli._ensure_fresh(False, False)
    err = capsys.readouterr().err
    assert "重建失败,沿用旧快照" in err
    assert "缺少 networkx" in err
    assert "[快照 old-snapshot]" in err

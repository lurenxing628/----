"""契约测试：死代码孤岛扫描必须区分“没被调用图确信解析”和“真的没人用”。"""

from __future__ import annotations

import json

from tools import scan_dead_code_islands
from tools.dead_code_usage import scip_usage
from tools.dead_code_usage.ast_usage import collect_ast_usage
from tools.dead_code_usage.model import records_from_functions
from tools.dead_code_usage.scip_usage import ScipUsageError
from tools.symbol_locator import cli, scip_deep


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _line(text, needle):
    for index, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return index
    raise AssertionError(needle)


def _sample_project(tmp_path):
    static_index = "\n".join([
        "class StaticIndex:",
        "    def lookup_name(self, name):",
        "        return []",
        "    def info(self, key):",
        "        return {}",
        "",
        "def load():",
        "    # type: () -> StaticIndex",
        "    return StaticIndex()",
        "",
        "def unused():",
        "    return None",
        "",
    ])
    render = "\n".join([
        "def render_whereis(name, index):",
        "    rows = index.lookup_name(name)",
        "    return index.info(rows[0]) if rows else None",
        "",
    ])
    cli_text = "\n".join([
        "import argparse",
        "from . import render, static_index",
        "",
        "def _parse_at(value):",
        "    return value",
        "",
        "def build_parser():",
        "    parser = argparse.ArgumentParser()",
        "    parser.add_argument('--at', type=_parse_at)",
        "    return parser",
        "",
        "def main():",
        "    index = static_index.load()",
        "    return render.render_whereis('foo', index)",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "static_index.py", static_index)
    _write(tmp_path / "pkg" / "render.py", render)
    _write(tmp_path / "pkg" / "cli.py", cli_text)
    functions = {
        "pkg/cli.py::_parse_at": {
            "rel": "pkg/cli.py",
            "line": _line(cli_text, "def _parse_at"),
            "end": _line(cli_text, "return value"),
            "cls": None,
            "name": "_parse_at",
        },
        "pkg/cli.py::main": {
            "rel": "pkg/cli.py",
            "line": _line(cli_text, "def main"),
            "end": _line(cli_text, "render.render_whereis"),
            "cls": None,
            "name": "main",
        },
        "pkg/render.py::render_whereis": {
            "rel": "pkg/render.py",
            "line": _line(render, "def render_whereis"),
            "end": _line(render, "return index.info"),
            "cls": None,
            "name": "render_whereis",
        },
        "pkg/static_index.py::load": {
            "rel": "pkg/static_index.py",
            "line": _line(static_index, "def load"),
            "end": _line(static_index, "return StaticIndex"),
            "cls": None,
            "name": "load",
        },
        "pkg/static_index.py::unused": {
            "rel": "pkg/static_index.py",
            "line": _line(static_index, "def unused"),
            "end": _line(static_index, "return None"),
            "cls": None,
            "name": "unused",
        },
        "pkg/static_index.py::StaticIndex.lookup_name": {
            "rel": "pkg/static_index.py",
            "line": _line(static_index, "def lookup_name"),
            "end": _line(static_index, "return []"),
            "cls": "StaticIndex",
            "name": "lookup_name",
        },
        "pkg/static_index.py::StaticIndex.info": {
            "rel": "pkg/static_index.py",
            "line": _line(static_index, "def info"),
            "end": _line(static_index, "return {}"),
            "cls": "StaticIndex",
            "name": "info",
        },
    }
    return functions


def test_ast_usage_graph_explains_callbacks_module_calls_and_typed_methods(tmp_path):
    functions = _sample_project(tmp_path)
    records = records_from_functions(functions)

    evidence = collect_ast_usage(str(tmp_path), records)

    assert evidence["pkg/cli.py::_parse_at"][0].kind == "name_reference"
    assert evidence["pkg/static_index.py::load"][0].kind == "module_attr_reference"
    assert evidence["pkg/static_index.py::StaticIndex.lookup_name"][0].kind == "typed_method_reference"
    assert evidence["pkg/static_index.py::StaticIndex.info"][0].kind == "typed_method_reference"
    assert "pkg/static_index.py::unused" not in evidence


def test_ast_usage_graph_does_not_cross_wire_same_named_classes(tmp_path):
    a_text = "\n".join([
        "class Client:",
        "    def ping(self):",
        "        return 'a'",
        "",
    ])
    b_text = "\n".join([
        "class Client:",
        "    def ping(self):",
        "        return 'b'",
        "",
        "def use_client():",
        "    client = Client()",
        "    return client.ping()",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", a_text)
    _write(tmp_path / "pkg" / "b.py", b_text)
    functions = {
        "pkg/a.py::Client.ping": {
            "rel": "pkg/a.py",
            "line": _line(a_text, "def ping"),
            "end": _line(a_text, "return 'a'"),
            "cls": "Client",
            "name": "ping",
        },
        "pkg/b.py::Client.ping": {
            "rel": "pkg/b.py",
            "line": _line(b_text, "def ping"),
            "end": _line(b_text, "return 'b'"),
            "cls": "Client",
            "name": "ping",
        },
        "pkg/b.py::use_client": {
            "rel": "pkg/b.py",
            "line": _line(b_text, "def use_client"),
            "end": _line(b_text, "client.ping"),
            "cls": None,
            "name": "use_client",
        },
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert "pkg/a.py::Client.ping" not in evidence
    assert evidence["pkg/b.py::Client.ping"][0].kind == "typed_method_reference"


def test_ast_usage_graph_respects_imported_class_binding_over_local_same_name(tmp_path):
    a_text = "\n".join([
        "class Client:",
        "    def ping(self):",
        "        return 'a'",
        "",
    ])
    b_text = "\n".join([
        "class Client:",
        "    def ping(self):",
        "        return 'b'",
        "",
        "from .a import Client",
        "",
        "def use_imported_client():",
        "    client = Client()",
        "    return client.ping()",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", a_text)
    _write(tmp_path / "pkg" / "b.py", b_text)
    functions = {
        "pkg/a.py::Client.ping": {
            "rel": "pkg/a.py",
            "line": _line(a_text, "def ping"),
            "end": _line(a_text, "return 'a'"),
            "cls": "Client",
            "name": "ping",
        },
        "pkg/b.py::Client.ping": {
            "rel": "pkg/b.py",
            "line": _line(b_text, "def ping"),
            "end": _line(b_text, "return 'b'"),
            "cls": "Client",
            "name": "ping",
        },
        "pkg/b.py::use_imported_client": {
            "rel": "pkg/b.py",
            "line": _line(b_text, "def use_imported_client"),
            "end": _line(b_text, "client.ping"),
            "cls": None,
            "name": "use_imported_client",
        },
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert evidence["pkg/a.py::Client.ping"][0].kind == "typed_method_reference"
    assert "pkg/b.py::Client.ping" not in evidence


def test_ast_usage_graph_ignores_local_variable_shadowing_function_name(tmp_path):
    text = "\n".join([
        "def victim():",
        "    return 'function'",
        "",
        "def other():",
        "    victim = 42",
        "    return victim",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "sample.py", text)
    functions = {
        "pkg/sample.py::victim": {
            "rel": "pkg/sample.py",
            "line": _line(text, "def victim"),
            "end": _line(text, "return 'function'"),
            "cls": None,
            "name": "victim",
        },
        "pkg/sample.py::other": {
            "rel": "pkg/sample.py",
            "line": _line(text, "def other"),
            "end": _line(text, "return victim"),
            "cls": None,
            "name": "other",
        },
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert "pkg/sample.py::victim" not in evidence


def test_ast_usage_graph_ignores_shadowed_direct_import_function(tmp_path):
    a_text = "\n".join([
        "def victim():",
        "    return 'function'",
        "",
    ])
    b_text = "\n".join([
        "from .a import victim",
        "",
        "def local_shadow():",
        "    victim = 42",
        "    return victim",
        "",
        "def parameter_shadow(victim):",
        "    return victim",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", a_text)
    _write(tmp_path / "pkg" / "b.py", b_text)
    functions = {
        "pkg/a.py::victim": {
            "rel": "pkg/a.py",
            "line": _line(a_text, "def victim"),
            "end": _line(a_text, "return 'function'"),
            "cls": None,
            "name": "victim",
        },
        "pkg/b.py::local_shadow": {
            "rel": "pkg/b.py",
            "line": _line(b_text, "def local_shadow"),
            "end": _line(b_text, "return victim"),
            "cls": None,
            "name": "local_shadow",
        },
        "pkg/b.py::parameter_shadow": {
            "rel": "pkg/b.py",
            "line": _line(b_text, "def parameter_shadow"),
            "end": _line(b_text, "return victim"),
            "cls": None,
            "name": "parameter_shadow",
        },
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert "pkg/a.py::victim" not in evidence


def test_ast_usage_graph_does_not_infer_type_from_later_assignment(tmp_path):
    text = "\n".join([
        "class Client:",
        "    def ping(self):",
        "        return 'method'",
        "",
        "def caller(obj):",
        "    obj.ping()",
        "    obj = Client()",
        "    return obj",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "sample.py", text)
    functions = {
        "pkg/sample.py::Client.ping": {
            "rel": "pkg/sample.py",
            "line": _line(text, "def ping"),
            "end": _line(text, "return 'method'"),
            "cls": "Client",
            "name": "ping",
        },
        "pkg/sample.py::caller": {
            "rel": "pkg/sample.py",
            "line": _line(text, "def caller"),
            "end": _line(text, "return obj"),
            "cls": None,
            "name": "caller",
        },
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert "pkg/sample.py::Client.ping" not in evidence


def test_ast_usage_graph_does_not_treat_shadowed_class_name_as_constructor(tmp_path):
    text = "\n".join([
        "class Client:",
        "    def ping(self):",
        "        return 'method'",
        "",
        "def caller(Client):",
        "    obj = Client()",
        "    return obj.ping()",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "sample.py", text)
    functions = {
        "pkg/sample.py::Client.ping": {
            "rel": "pkg/sample.py",
            "line": _line(text, "def ping"),
            "end": _line(text, "return 'method'"),
            "cls": "Client",
            "name": "ping",
        },
        "pkg/sample.py::caller": {
            "rel": "pkg/sample.py",
            "line": _line(text, "def caller"),
            "end": _line(text, "return obj.ping"),
            "cls": None,
            "name": "caller",
        },
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert "pkg/sample.py::Client.ping" not in evidence


def test_quick_scan_reports_only_unexplained_suspects(tmp_path, monkeypatch):
    functions = _sample_project(tmp_path)
    monkeypatch.setattr(scan_dead_code_islands, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(
        scan_dead_code_islands,
        "_compute_callgraph_snapshot",
        lambda: {
            "functions": functions,
            "edges": [],
            "islands": [qual for qual in functions if qual != "pkg/cli.py::main"],
        },
    )

    result = scan_dead_code_islands._analyze("quick", None)

    assert result["mode"] == "quick"
    assert result["suspect_dead"] == ["pkg/static_index.py::unused"]


def test_scan_failure_is_not_silent_even_when_warn_only(monkeypatch, capsys):
    monkeypatch.setattr(scan_dead_code_islands, "_compute_callgraph_snapshot", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    assert scan_dead_code_islands.main(["--warn-only"]) == 2
    assert "扫描失败" in capsys.readouterr().out


def test_warn_only_only_changes_new_suspect_exit_code(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"islands": []}), encoding="utf-8")
    monkeypatch.setattr(scan_dead_code_islands, "BASELINE_PATH", str(baseline))
    monkeypatch.setattr(scan_dead_code_islands, "BASELINE_REL", "baseline.json")
    monkeypatch.setattr(
        scan_dead_code_islands,
        "_analyze",
        lambda _mode, _index_path: {
            "mode": "quick",
            "candidate_count": 1,
            "live_count": 0,
            "suspect_dead": ["x.py::unused"],
            "evidence": {},
        },
    )

    assert scan_dead_code_islands.main([]) == 1
    assert scan_dead_code_islands.main(["--warn-only"]) == 0


def test_refresh_records_selected_mode_and_matching_command(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    monkeypatch.setattr(scan_dead_code_islands, "BASELINE_PATH", str(baseline))
    monkeypatch.setattr(scan_dead_code_islands, "BASELINE_REL", "baseline.json")
    monkeypatch.setattr(
        scan_dead_code_islands,
        "_analyze",
        lambda mode, _index_path: {
            "mode": mode,
            "candidate_count": 1,
            "live_count": 0,
            "suspect_dead": ["x.py::unused"],
            "evidence": {},
        },
    )

    assert scan_dead_code_islands.main(["--mode", "quick", "--refresh"]) == 0
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["mode"] == "quick"
    assert "--mode quick --refresh" in payload["note"]
    assert "--mode precise --refresh" not in payload["note"]


def test_precise_mode_failure_is_loud_and_not_downgraded(monkeypatch, capsys):
    monkeypatch.setattr(scan_dead_code_islands, "_compute_callgraph_snapshot", lambda: {"functions": {}, "edges": [], "islands": []})

    def fail(_repo_root, _records, index_path=None):
        raise ScipUsageError("stale_index", "SCIP 索引不是当前 HEAD。", ["重新运行: python -m tools.symbol_locator build-index"])

    monkeypatch.setattr(scan_dead_code_islands, "_collect_scip_usage", fail)

    assert scan_dead_code_islands.main(["--mode", "precise"]) == 2
    out = capsys.readouterr().out
    assert "精确模式不可用" in out
    assert "build-index" in out


def test_precise_dirty_worktree_message_does_not_suggest_staging(monkeypatch, tmp_path):
    monkeypatch.setattr(scip_usage, "_git_dirty", lambda _repo_root: True)

    try:
        scip_usage._require_fresh_index(str(tmp_path))
    except ScipUsageError as exc:
        assert exc.code == "dirty_worktree"
        assert "清理当前改动" in "\n".join(exc.hints)
        assert "暂存" not in "\n".join(exc.hints)
    else:
        raise AssertionError("dirty worktree must fail precise mode")


def test_symbol_locator_build_index_has_explicit_cli(monkeypatch, capsys):
    def fake_build_index(index_path=None, stdout=None):
        print("indexing progress", file=stdout)
        return index_path or "index.scip"

    monkeypatch.setattr(scip_deep, "build_index", fake_build_index)

    assert cli.main(["build-index", "--output", "tmp.scip", "--json"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload == {"engine": "scip", "index": "tmp.scip"}
    assert "indexing progress" in captured.err

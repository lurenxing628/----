"""契约测试：AST 使用图必须遵守 Python 名字绑定规则。"""

from __future__ import annotations

from tools.dead_code_usage import scip_usage
from tools.dead_code_usage.ast_usage import collect_ast_usage
from tools.dead_code_usage.model import records_from_functions


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _line(text, needle):
    for index, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return index
    raise AssertionError(needle)


def _function(rel, text, name, cls=None):
    needle = f"def {name}"
    return {
        "rel": rel,
        "line": _line(text, needle),
        "end": len(text.splitlines()),
        "cls": cls,
        "name": name,
    }


def test_later_local_assignment_shadows_whole_function(tmp_path):
    a_text = "\n".join([
        "def victim():",
        "    return 'function'",
        "",
    ])
    b_text = "\n".join([
        "from .a import victim",
        "",
        "def caller():",
        "    victim()",
        "    victim = 42",
        "    return victim",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", a_text)
    _write(tmp_path / "pkg" / "b.py", b_text)
    functions = {
        "pkg/a.py::victim": _function("pkg/a.py", a_text, "victim"),
        "pkg/b.py::caller": _function("pkg/b.py", b_text, "caller"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert "pkg/a.py::victim" not in evidence


def test_later_local_bindings_shadow_whole_function(tmp_path):
    a_text = "\n".join([
        "def victim():",
        "    return 'function'",
        "",
    ])
    cases = [
        [
            "from .a import victim",
            "",
            "def caller():",
            "    victim()",
            "    def victim():",
            "        return 'local'",
            "    return victim",
            "",
        ],
        [
            "from .a import victim",
            "",
            "def caller():",
            "    victim()",
            "    class victim:",
            "        pass",
            "    return victim",
            "",
        ],
        [
            "from .a import victim",
            "",
            "def caller():",
            "    victim()",
            "    victim += 1",
            "    return victim",
            "",
        ],
        [
            "from .a import victim",
            "",
            "def caller():",
            "    victim()",
            "    return (victim := 42)",
            "",
        ],
    ]
    for index, lines in enumerate(cases):
        package = f"pkg_{index}"
        b_text = "\n".join(lines)
        rel = f"{package}/case.py"
        _write(tmp_path / package / "__init__.py", "")
        _write(tmp_path / package / "a.py", a_text)
        _write(tmp_path / package / "case.py", b_text)
        functions = {
            f"{package}/a.py::victim": _function(f"{package}/a.py", a_text, "victim"),
            f"{rel}::caller": _function(rel, b_text, "caller"),
        }

        evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

        assert f"{package}/a.py::victim" not in evidence


def test_function_local_import_is_real_usage(tmp_path):
    a_text = "\n".join([
        "def target():",
        "    return 'ok'",
        "",
    ])
    b_text = "\n".join([
        "def caller():",
        "    from .a import target",
        "    return target()",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", a_text)
    _write(tmp_path / "pkg" / "b.py", b_text)
    functions = {
        "pkg/a.py::target": _function("pkg/a.py", a_text, "target"),
        "pkg/b.py::caller": _function("pkg/b.py", b_text, "caller"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert evidence["pkg/a.py::target"][0].kind == "name_reference"


def test_module_without_functions_can_register_callback_usage(tmp_path):
    callback_text = "\n".join([
        "def callback():",
        "    return 'ok'",
        "",
    ])
    registry_text = "\n".join([
        "from .callbacks import callback",
        "",
        "HANDLERS = [callback]",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "callbacks.py", callback_text)
    _write(tmp_path / "pkg" / "registry.py", registry_text)
    functions = {
        "pkg/callbacks.py::callback": _function("pkg/callbacks.py", callback_text, "callback"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert evidence["pkg/callbacks.py::callback"][0].source_rel == "pkg/registry.py"


def test_comprehension_target_does_not_count_as_imported_function_usage(tmp_path):
    a_text = "\n".join([
        "def victim():",
        "    return 'function'",
        "",
    ])
    b_text = "\n".join([
        "from .a import victim",
        "",
        "def caller(rows):",
        "    return [victim for victim in rows]",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", a_text)
    _write(tmp_path / "pkg" / "b.py", b_text)
    functions = {
        "pkg/a.py::victim": _function("pkg/a.py", a_text, "victim"),
        "pkg/b.py::caller": _function("pkg/b.py", b_text, "caller"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert "pkg/a.py::victim" not in evidence


def test_comprehension_input_keeps_imported_function_usage(tmp_path):
    a_text = "\n".join([
        "def victim():",
        "    return []",
        "",
    ])
    b_text = "\n".join([
        "from .a import victim",
        "",
        "def caller():",
        "    value = 1",
        "    return [value for victim in victim()]",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", a_text)
    _write(tmp_path / "pkg" / "b.py", b_text)
    functions = {
        "pkg/a.py::victim": _function("pkg/a.py", a_text, "victim"),
        "pkg/b.py::caller": _function("pkg/b.py", b_text, "caller"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert evidence["pkg/a.py::victim"][0].kind == "name_reference"


def test_unknown_reassignment_clears_previous_local_type(tmp_path):
    text = "\n".join([
        "class Client:",
        "    def ping(self):",
        "        return 'method'",
        "",
        "def caller():",
        "    client = Client()",
        "    client = object()",
        "    return client.ping()",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "sample.py", text)
    functions = {
        "pkg/sample.py::Client.ping": _function("pkg/sample.py", text, "ping", cls="Client"),
        "pkg/sample.py::caller": _function("pkg/sample.py", text, "caller"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert "pkg/sample.py::Client.ping" not in evidence


def test_package_init_module_registration_resolves_relative_import(tmp_path):
    target_text = "\n".join([
        "def target():",
        "    return 'ok'",
        "",
    ])
    init_text = "\n".join([
        "from .a import target",
        "HANDLERS = [target]",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", init_text)
    _write(tmp_path / "pkg" / "a.py", target_text)
    functions = {
        "pkg/a.py::target": _function("pkg/a.py", target_text, "target"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert evidence["pkg/a.py::target"][0].source_rel == "pkg/__init__.py"


def test_same_line_package_init_registration_uses_import_alias(tmp_path):
    target_text = "\n".join([
        "def target():",
        "    return 'ok'",
        "",
    ])
    init_text = "from .a import target; HANDLERS = [target]\n"
    _write(tmp_path / "pkg" / "__init__.py", init_text)
    _write(tmp_path / "pkg" / "a.py", target_text)
    functions = {
        "pkg/a.py::target": _function("pkg/a.py", target_text, "target"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert evidence["pkg/a.py::target"][0].source_rel == "pkg/__init__.py"


def test_same_line_module_rebinding_clears_import_alias_before_later_use(tmp_path):
    callback_text = "\n".join([
        "def callback():",
        "    return 'ok'",
        "",
    ])
    registry_text = "from .callbacks import callback; callback = None; HANDLERS = [callback]\n"
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "callbacks.py", callback_text)
    _write(tmp_path / "pkg" / "registry.py", registry_text)
    functions = {
        "pkg/callbacks.py::callback": _function("pkg/callbacks.py", callback_text, "callback"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert "pkg/callbacks.py::callback" not in evidence


def test_module_alias_class_constructor_marks_init_usage(tmp_path):
    a_text = "\n".join([
        "class Client:",
        "    def __init__(self):",
        "        self.ready = True",
        "",
    ])
    b_text = "\n".join([
        "from . import a",
        "",
        "def caller():",
        "    return a.Client()",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", a_text)
    _write(tmp_path / "pkg" / "b.py", b_text)
    functions = {
        "pkg/a.py::Client.__init__": _function("pkg/a.py", a_text, "__init__", cls="Client"),
        "pkg/b.py::caller": _function("pkg/b.py", b_text, "caller"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert evidence["pkg/a.py::Client.__init__"][0].kind == "constructor_call"


def test_same_line_local_rebinding_clears_import_alias_before_later_use(tmp_path):
    target_text = "\n".join([
        "def target():",
        "    return 'ok'",
        "",
    ])
    caller_text = "\n".join([
        "def caller():",
        "    from .a import target; target = None; return target()",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", target_text)
    _write(tmp_path / "pkg" / "caller.py", caller_text)
    functions = {
        "pkg/a.py::target": _function("pkg/a.py", target_text, "target"),
        "pkg/caller.py::caller": _function("pkg/caller.py", caller_text, "caller"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert "pkg/a.py::target" not in evidence


def test_same_line_local_module_import_feeds_class_constructor(tmp_path):
    a_text = "\n".join([
        "class Client:",
        "    def __init__(self):",
        "        self.ready = True",
        "",
    ])
    b_text = "\n".join([
        "def caller():",
        "    from . import a; return a.Client()",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", a_text)
    _write(tmp_path / "pkg" / "b.py", b_text)
    functions = {
        "pkg/a.py::Client.__init__": _function("pkg/a.py", a_text, "__init__", cls="Client"),
        "pkg/b.py::caller": _function("pkg/b.py", b_text, "caller"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert evidence["pkg/a.py::Client.__init__"][0].kind == "constructor_call"


def test_module_registration_before_rebinding_keeps_imported_function_usage(tmp_path):
    callback_text = "\n".join([
        "def callback():",
        "    return 'ok'",
        "",
    ])
    registry_text = "\n".join([
        "from .callbacks import callback",
        "HANDLERS = [callback]",
        "callback = None",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "callbacks.py", callback_text)
    _write(tmp_path / "pkg" / "registry.py", registry_text)
    functions = {
        "pkg/callbacks.py::callback": _function("pkg/callbacks.py", callback_text, "callback"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert evidence["pkg/callbacks.py::callback"][0].source_rel == "pkg/registry.py"


def test_module_rebinding_clears_imported_function_and_class_alias(tmp_path):
    a_text = "\n".join([
        "def victim():",
        "    return 'function'",
        "",
        "class Client:",
        "    def ping(self):",
        "        return 'method'",
        "",
    ])
    b_text = "\n".join([
        "from .a import Client, victim",
        "victim = 42",
        "Client = object",
        "",
        "def reader():",
        "    return victim",
        "",
        "def caller():",
        "    obj = Client()",
        "    return obj.ping()",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", a_text)
    _write(tmp_path / "pkg" / "b.py", b_text)
    functions = {
        "pkg/a.py::victim": _function("pkg/a.py", a_text, "victim"),
        "pkg/a.py::Client.ping": _function("pkg/a.py", a_text, "ping", cls="Client"),
        "pkg/b.py::reader": _function("pkg/b.py", b_text, "reader"),
        "pkg/b.py::caller": _function("pkg/b.py", b_text, "caller"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert "pkg/a.py::victim" not in evidence
    assert "pkg/a.py::Client.ping" not in evidence


def test_module_alias_class_constructor_feeds_typed_method_reference(tmp_path):
    a_text = "\n".join([
        "class Client:",
        "    def ping(self):",
        "        return 'method'",
        "",
    ])
    b_text = "\n".join([
        "from . import a",
        "",
        "def caller():",
        "    client = a.Client()",
        "    return client.ping()",
        "",
    ])
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", a_text)
    _write(tmp_path / "pkg" / "b.py", b_text)
    functions = {
        "pkg/a.py::Client.ping": _function("pkg/a.py", a_text, "ping", cls="Client"),
        "pkg/b.py::caller": _function("pkg/b.py", b_text, "caller"),
    }

    evidence = collect_ast_usage(str(tmp_path), records_from_functions(functions))

    assert evidence["pkg/a.py::Client.ping"][0].kind == "typed_method_reference"


def test_precise_scip_usage_ignores_import_only_references(tmp_path):
    symbol = "scip-python python aps version `pkg.a`/target()."
    _write(tmp_path / "pkg" / "a.py", "def target():\n    return None\n")
    _write(tmp_path / "pkg" / "b.py", "from .a import target\nHANDLERS = [target]\n")
    docs = [{
        "relative_path": "pkg/b.py",
        "occurrences": [
            {"range": [0, 15, 21], "symbol": symbol, "symbol_roles": 8},
            {"range": [1, 12, 18], "symbol": symbol, "symbol_roles": 8},
        ],
    }]

    evidence = scip_usage._references_for_symbols(str(tmp_path), docs, {"pkg/a.py::target": {symbol}})

    assert [(item.source_rel, item.line) for item in evidence["pkg/a.py::target"]] == [("pkg/b.py", 2)]
    docs[0]["occurrences"] = docs[0]["occurrences"][:1]
    assert scip_usage._references_for_symbols(str(tmp_path), docs, {"pkg/a.py::target": {symbol}}) == {}

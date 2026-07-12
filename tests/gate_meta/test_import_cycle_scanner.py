from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from tests._support.paths import REPO_ROOT
from tools import scan_import_cycles
from tools.import_cycle_analysis import classify, dyn_imports


def _classified_imports(source: str) -> Dict[str, str]:
    rows: Dict[str, str] = {}
    for node, context in classify(ast.parse(source)):
        if isinstance(node, ast.Import):
            rows[node.names[0].name] = context
        elif isinstance(node, ast.ImportFrom):
            rows[str(node.module)] = context
    return rows


def test_static_import_context_covers_loops_with_conditions_try_classes_and_functions() -> None:
    contexts = _classified_imports(
        """
from typing import TYPE_CHECKING
import hard_direct
for item in ():
    import hard_for
else:
    import hard_for_else
while False:
    import hard_while
with manager():
    import hard_with
if enabled:
    import conditional_if
try:
    import conditional_try
except Exception:
    import conditional_except
finally:
    import hard_finally
if TYPE_CHECKING:
    import type_only
else:
    import hard_type_else
class Contract:
    for item in ():
        import hard_class_for
    if enabled:
        import conditional_class_if
async def worker():
    for item in ():
        import lazy_for
    async for item in stream():
        import lazy_async_for
    while enabled:
        import lazy_while
    with manager():
        import lazy_with
    async with async_manager():
        import lazy_async_with
    if enabled:
        import lazy_if
    try:
        import lazy_try
    finally:
        import lazy_finally
    if TYPE_CHECKING:
        import type_only_in_function
    else:
        import lazy_type_else
"""
    )

    assert contexts == {
        "typing": "hard",
        "hard_direct": "hard",
        "hard_for": "hard",
        "hard_for_else": "hard",
        "hard_while": "hard",
        "hard_with": "hard",
        "conditional_if": "cond",
        "conditional_try": "cond",
        "conditional_except": "cond",
        "hard_finally": "hard",
        "type_only": "typeonly",
        "hard_type_else": "hard",
        "hard_class_for": "hard",
        "conditional_class_if": "cond",
        "lazy_for": "lazy",
        "lazy_async_for": "lazy",
        "lazy_while": "lazy",
        "lazy_with": "lazy",
        "lazy_async_with": "lazy",
        "lazy_if": "lazy",
        "lazy_try": "lazy",
        "lazy_finally": "lazy",
        "type_only_in_function": "typeonly",
        "lazy_type_else": "lazy",
    }


def test_dynamic_imports_keep_context_and_report_non_literal_targets_without_guessing() -> None:
    resolved, unresolved = dyn_imports(
        ast.parse(
            """
from typing import TYPE_CHECKING
import importlib
importlib.import_module("core.fixed")
if enabled:
    importlib.import_module("core.conditional")
if TYPE_CHECKING:
    importlib.import_module("core.type_only")
else:
    importlib.import_module("core.runtime_else")
module_name = "core.variable"
importlib.import_module(module_name)
importlib.import_module("core." + suffix)
def load_later():
    while enabled:
        importlib.import_module("core.lazy")
        importlib.import_module(module_name)
"""
        )
    )

    assert set(resolved) == {
        ("core.fixed", None, "hard", 4),
        ("core.conditional", None, "cond", 6),
        ("core.type_only", None, "typeonly", 8),
        ("core.runtime_else", None, "hard", 10),
        ("core.lazy", None, "lazy", 16),
    }
    assert {(context, line) for context, line, _expression in unresolved} == {
        ("hard", 12),
        ("hard", 13),
        ("lazy", 17),
    }
    expressions = [expression for _context, _line, expression in unresolved]
    assert any("module_name" in expression for expression in expressions)
    assert any("suffix" in expression for expression in expressions)
    assert all("core.variable" not in expression for expression in expressions)


def test_dynamic_loader_variants_resolve_dunder_import_and_report_file_loader() -> None:
    resolved, unresolved = dyn_imports(
        ast.parse(
            """
import importlib
import importlib.metadata
import importlib.util
__import__("pkg.fixed")
__import__(module_name)
importlib.util.spec_from_file_location(module_name, plugin_path)
"""
        )
    )

    assert resolved == [("pkg.fixed", None, "hard", 5)]
    assert unresolved == [
        ("hard", 6, "__import__(module_name)"),
        ("hard", 7, "spec_from_file_location(module_name)"),
    ]


def test_dynamic_loader_aliases_and_keyword_arguments_are_not_silent() -> None:
    resolved, unresolved = dyn_imports(
        ast.parse(
            """
import importlib as il
from importlib import import_module as load
from importlib.util import spec_from_file_location as spec_load
il.import_module("pkg.absolute")
load(name="pkg.keyword")
il.import_module(name=".relative", package="pkg")
spec_load(name="plugin_name", location=plugin_path)
"""
        )
    )

    assert resolved == [
        ("pkg.absolute", None, "hard", 5),
        ("pkg.keyword", None, "hard", 6),
        (".relative", "pkg", "hard", 7),
    ]
    assert unresolved == [
        ("hard", 8, "spec_from_file_location('plugin_name')"),
    ]


def test_dynamic_import_alias_forms_a_real_scanned_cycle(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "a.py").write_text(
        'import importlib as il\nil.import_module("pkg.b")\n',
        encoding="utf-8",
    )
    (package / "b.py").write_text("import pkg.a\n", encoding="utf-8")

    result = scan_import_cycles.scan(["pkg"], repo_root=str(tmp_path))

    assert any(set(cycle["members"]) == {"pkg.a", "pkg.b"} for cycle in result["explicit_hard_file_cycles"])
    assert result["unresolved_dynamic_imports"] == []


def test_dynamic_loader_shadowing_is_scoped_without_poisoning_proven_aliases() -> None:
    resolved, unresolved = dyn_imports(
        ast.parse(
            """
import importlib as loader
loader.import_module("pkg.top")
def shadowed(loader):
    loader.import_module("pkg.shadowed")
def local_loader():
    import importlib as inner
    inner.import_module("pkg.inner")
"""
        )
    )

    assert resolved == [
        ("pkg.top", None, "hard", 3),
        ("pkg.inner", None, "lazy", 8),
    ]
    assert len(unresolved) == 1
    context, line, expression = unresolved[0]
    assert (context, line) == ("lazy", 5)
    assert "unproven loader binding" in expression
    assert "pkg.shadowed" in expression


def test_dynamic_loader_rebinding_forms_are_unresolved() -> None:
    cases = [
        (
            'import importlib as loader\nloader = object()\nloader.import_module("pkg.target")\n',
            "hard",
        ),
        (
            'import importlib as loader\nloader.import_module("pkg.target")\nloader = object()\n',
            "hard",
        ),
        (
            'from importlib import import_module as load\nload = object()\nload("pkg.target")\n',
            "hard",
        ),
        (
            'import importlib as loader\nfor loader in values:\n    loader.import_module("pkg.target")\n',
            "hard",
        ),
        (
            'import importlib as loader\nwith manager() as loader:\n    loader.import_module("pkg.target")\n',
            "hard",
        ),
        (
            'import importlib as loader\ntry:\n    pass\nexcept Exception as loader:\n    loader.import_module("pkg.target")\n',
            "cond",
        ),
        (
            'import importlib as loader\ndef loader():\n    pass\nloader.import_module("pkg.target")\n',
            "hard",
        ),
        (
            'import importlib as loader\nclass loader:\n    pass\nloader.import_module("pkg.target")\n',
            "hard",
        ),
        (
            'import importlib as loader\ndel loader\nloader.import_module("pkg.target")\n',
            "hard",
        ),
        (
            'import importlib as loader\ndef load(loader):\n    loader.import_module("pkg.target")\n',
            "lazy",
        ),
        (
            'def load(__import__):\n    __import__("pkg.target")\n',
            "lazy",
        ),
    ]

    for source, expected_context in cases:
        resolved, unresolved = dyn_imports(ast.parse(source))

        assert resolved == []
        assert len(unresolved) == 1
        context, _line, expression = unresolved[0]
        assert context == expected_context
        assert "unproven loader binding" in expression
        assert "pkg.target" in expression


def test_rebound_dynamic_loader_alias_does_not_form_false_scanned_cycle(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "a.py").write_text(
        'import importlib as loader\nloader = object()\nloader.import_module("pkg.b")\n',
        encoding="utf-8",
    )
    (package / "b.py").write_text("import pkg.a\n", encoding="utf-8")

    result = scan_import_cycles.scan(["pkg"], repo_root=str(tmp_path))

    assert result["explicit_hard_file_cycles"] == []
    assert result["unresolved_dynamic_imports"] == [
        {
            "file": "pkg/a.py",
            "line": 3,
            "context": "hard",
            "expression": "unproven loader binding: loader.import_module('pkg.b')",
        }
    ]


def test_scan_reports_unresolved_dynamic_imports_with_file_line_and_context(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "target.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "source.py").write_text(
        """
import importlib
name = "pkg.target"
importlib.import_module("pkg.target")
importlib.import_module(name)
def later():
    importlib.import_module("pkg." + "target")
""",
        encoding="utf-8",
    )

    result = scan_import_cycles.scan(["pkg"], repo_root=str(tmp_path))

    assert result["parse_errors"] == []
    assert result["edge_counts"]["hard"] == 2
    assert result["unresolved_dynamic_imports"] == [
        {
            "file": "pkg/source.py",
            "line": 5,
            "context": "hard",
            "expression": "name",
        },
        {
            "file": "pkg/source.py",
            "line": 7,
            "context": "lazy",
            "expression": "'pkg.' Add 'target'",
        },
    ]
    text = scan_import_cycles.render_text(result)
    assert "pkg/source.py:5 [hard] name" in text
    assert "pkg/source.py:7 [lazy] 'pkg.' Add 'target'" in text


def test_relative_literal_dynamic_import_uses_current_package_and_records_hard_edge(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "target.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "source.py").write_text(
        'import importlib\nimportlib.import_module(".target", __package__)\n',
        encoding="utf-8",
    )

    result = scan_import_cycles.scan(["pkg"], repo_root=str(tmp_path))

    assert result["parse_errors"] == []
    assert result["edge_counts"]["hard"] == 2
    assert result["unresolved_dynamic_imports"] == []


def test_parent_package_initialization_edge_exposes_real_file_cycle(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (tmp_path / "app.py").write_text(
        "from pkg.sub import VALUE\nAPP_READY = True\n",
        encoding="utf-8",
    )
    (package / "__init__.py").write_text("from app import APP_READY\n", encoding="utf-8")
    (package / "sub.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = scan_import_cycles.scan(["app.py", "pkg"], repo_root=str(tmp_path))

    cycle_members = {frozenset(cycle) for cycle in result["hard_file_cycles"]}
    assert frozenset({"app", "pkg"}) in cycle_members
    assert result["explicit_hard_file_cycles"] == []
    record = next(
        cycle for cycle in result["hard_file_cycle_records"] if set(cycle["members"]) == {"app", "pkg"}
    )
    assert {f"{edge['source']} -> {edge['target']}" for edge in record["edges"]} == {
        "app -> pkg",
        "pkg -> app",
    }


def test_dynamic_package_getattr_with_name_package_is_auditable_runtime_cycle(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (tmp_path / "app.py").write_text("from pkg import VALUE\nREADY = True\n", encoding="utf-8")
    (package / "__init__.py").write_text(
        """
import importlib
def __getattr__(name):
    return importlib.import_module(".impl", __name__).VALUE
""",
        encoding="utf-8",
    )
    (package / "impl.py").write_text("from app import READY\nVALUE = 1\n", encoding="utf-8")

    result = scan_import_cycles.scan(["app.py", "pkg"], repo_root=str(tmp_path))

    assert result["hard_file_cycles"] == []
    assert any(
        set(cycle["members"]) == {"app", "pkg", "pkg.impl"}
        for cycle in result["runtime_file_cycles"]
    )
    assert result["unresolved_dynamic_imports"] == []


def test_index_modules_supports_top_level_glob_and_plugins(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / "sample.py").write_text("VALUE = 2\n", encoding="utf-8")

    _files, modules = scan_import_cycles._index_modules(["*.py", "plugins"], str(tmp_path))

    assert set(modules) == {"app", "plugins.sample"}


def test_known_scheduler_loop_import_is_recorded_as_lazy() -> None:
    repo_root = str(REPO_ROOT)
    file_to_mod, mod_to_file = scan_import_cycles._index_modules(scan_import_cycles.PROD_ROOTS, repo_root)
    source_path = REPO_ROOT / "core/services/scheduler/run/schedule_graph_resource_matching_context.py"
    source_abs = str(source_path)
    source_mod = file_to_mod[source_abs]
    target_mod = "core.services.scheduler.graph.input_adapter"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    edges_file = {kind: defaultdict(list) for kind in scan_import_cycles.KINDS}
    explicit_edges_file = {kind: defaultdict(list) for kind in scan_import_cycles.KINDS}
    edges_dir = {kind: defaultdict(list) for kind in scan_import_cycles.KINDS}
    unresolved: List[dict] = []

    scan_import_cycles._collect_module_edges(
        source_abs,
        source_mod,
        tree,
        file_to_mod,
        mod_to_file,
        edges_file,
        explicit_edges_file,
        edges_dir,
        unresolved,
        [],
        repo_root,
    )

    locations: List[Tuple[str, int]] = edges_file["lazy"][(source_mod, target_mod)]
    assert ("core/services/scheduler/run/schedule_graph_resource_matching_context.py", 31) in locations
    assert ("core/services/scheduler/run/schedule_graph_resource_matching_context.py", 41) in locations
    assert (source_mod, target_mod) not in edges_file["hard"]
    assert (source_mod, target_mod) not in edges_file["cond"]

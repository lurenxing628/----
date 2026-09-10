"""Static import proofs use lexical bindings and real source paths only."""

import ast
from collections import defaultdict
from pathlib import Path
from typing import List

import pytest

from tests._support.paths import REPO_ROOT
from tools import import_cycle_graph, scan_import_cycles
from tools.import_cycle_analysis import dyn_imports


def test_literal_bindings_preserve_aliases_scopes_and_contexts() -> None:
    source = '''
from importlib import import_module as load
MODULE: str = "pkg.global_target"
def shadowed(MODULE):
    load(MODULE)
def valid():
    local = "pkg.local_target"
    load(local)
    load(MODULE)
class Example:
    MODULE = "pkg.class_target"
    load(MODULE)
    def method(self):
        load(MODULE)
if enabled:
    load(MODULE)
'''
    resolved, unresolved = dyn_imports(ast.parse(source))

    assert resolved == [
        ("pkg.local_target", None, "lazy", 8),
        ("pkg.global_target", None, "lazy", 9),
        ("pkg.class_target", None, "hard", 12),
        ("pkg.global_target", None, "lazy", 14),
        ("pkg.global_target", None, "cond", 16),
    ]
    assert unresolved == [("lazy", 5, "MODULE")]


@pytest.mark.parametrize("source", [
    'TARGET = "pkg.target"\nTARGET = "pkg.other"\nload(TARGET)',
    'TARGET = "pkg.target"\nload(TARGET)\nTARGET = dynamic()',
    'TARGET = "pkg.target"\nTARGET += suffix\nload(TARGET)',
    'TARGET = "pkg.target"\ndel TARGET\nload(TARGET)',
    'TARGET = "pkg.target"\nfor TARGET in names:\n    load(TARGET)',
    'TARGET = "pkg.target"\nwith context() as TARGET:\n    load(TARGET)',
    'TARGET = "pkg.target"\ntry:\n    pass\nexcept Exception as TARGET:\n    load(TARGET)',
    'TARGET = "pkg.target"\ndef TARGET():\n    pass\nload(TARGET)',
    'TARGET = "pkg.target"\nclass TARGET:\n    pass\nload(TARGET)',
    'TARGET = "pkg.target"\nfrom other import TARGET\nload(TARGET)',
    'TARGET = "pkg.target"\ndef run(TARGET):\n    load(TARGET)',
    'TARGET = "pkg.target"\ndef run(*, TARGET):\n    load(TARGET)',
    'TARGET = "pkg.target"\ndef run():\n    load(TARGET)\n    TARGET = "pkg.other"',
    'TARGET = "pkg.target"\ndef mutate():\n    global TARGET\n    TARGET = dynamic()\nload(TARGET)',
    'def run():\n    TARGET = "pkg.target"\n    def mutate():\n        nonlocal TARGET\n        TARGET = dynamic()\n    load(TARGET)',
    'if enabled:\n    TARGET = "pkg.target"\nload(TARGET)',
    'load(TARGET)\nTARGET = "pkg.target"',
    'TARGET = "pkg.target"\n[load(TARGET) for TARGET in names]',
    'TARGET = "pkg.target"\nTARGET, other = names\nload(TARGET)',
    'TARGET = dynamic()\nload(TARGET)',
    'TARGET = "pkg." + suffix\nload(TARGET)',
    'TARGET = "pkg.target"\nfrom other import *\nload(TARGET)',
    'TARGET = "pkg.target"\nload = custom\nload(TARGET)',
])
def test_rebound_shadowed_and_dynamic_values_stay_unresolved(source: str) -> None:
    resolved, unresolved = dyn_imports(ast.parse("from importlib import import_module as load\n" + source))

    assert resolved == []
    assert len(unresolved) == 1
    assert "TARGET" in unresolved[0][2]


def test_literal_relative_package_and_import_alias_are_proven() -> None:
    source = '''
import importlib as il
NAME = ".target"
PACKAGE = "pkg"
il.import_module(name=NAME, package=PACKAGE)
'''
    assert dyn_imports(ast.parse(source)) == ([(".target", "pkg", "hard", 5)], [])


def test_relative_and_rebound_loader_aliases_are_not_trusted() -> None:
    relative = 'from .importlib import import_module as load\nload("pkg.target")'
    rebound = 'import importlib as il\nil.import_module = custom\nil.import_module("pkg.target")'
    assert dyn_imports(ast.parse(relative))[0] == []
    resolved, unresolved = dyn_imports(ast.parse(rebound))
    assert resolved == []
    assert len(unresolved) == 1
    assert "unproven loader binding" in unresolved[0][2]


def _file_scan(tmp_path: Path, source: str) -> dict:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("raise RuntimeError('must not execute')\n", encoding="utf-8")
    (package / "source.py").write_text(source, encoding="utf-8")
    (package / "target.py").write_text("import pkg.source\n", encoding="utf-8")
    (package / "decoy.py").write_text("VALUE = 1\n", encoding="utf-8")
    return scan_import_cycles.scan(["pkg"], repo_root=str(tmp_path))


@pytest.mark.parametrize("path_import,expression", [
    ("from pathlib import Path", 'Path(__file__).resolve().parents[0] / "target.py"'),
    ("from pathlib import Path as P", 'P(__file__).resolve().parent / "target.py"'),
    ("import pathlib as pl", 'pl.Path(__file__).parent / "target.py"'),
])
def test_file_spec_uses_source_path_not_load_label_or_parent_initializers(
    tmp_path: Path, path_import: str, expression: str,
) -> None:
    source = ("from importlib.util import spec_from_file_location as spec\n" + path_import + "\n"
              + "SOURCE = " + expression + '\nspec(name="pkg.decoy", location=SOURCE)\n')
    result = _file_scan(tmp_path, source)

    assert result["parse_errors"] == []
    assert result["unresolved_dynamic_imports"] == []
    cycles = result["explicit_hard_file_cycles"]
    assert len(cycles) == 1
    assert set(cycles[0]["members"]) == {"pkg.source", "pkg.target"}
    assert {(row["source"], row["target"]) for row in cycles[0]["edges"]} == {
        ("pkg.source", "pkg.target"), ("pkg.target", "pkg.source"),
    }
    assert not any(row["source"] == "pkg.source" for row in result["parent_package_init_edges"])


@pytest.mark.parametrize("body", [
    'spec("pkg.target", plugin_path)',
    'spec("pkg.target", Path("target.py"))',
    'spec("pkg.target", Path("target.py").resolve())',
    'spec("pkg.target", Path(__file__).parent / filename)',
    'spec("pkg.target", Path(__file__).parent / "missing.py")',
    'spec("pkg.target", Path(__file__).parent / "target.py", loader=custom)',
    'Path = custom\nspec("pkg.target", Path(__file__).parent / "target.py")',
    'def run(Path):\n    spec("pkg.target", Path(__file__).parent / "target.py")',
    'def run(__file__):\n    spec("pkg.target", Path(__file__).parent / "target.py")',
    'def mutate():\n    global Path\n    Path = custom\nspec("pkg.target", Path(__file__).parent / "target.py")',
    'ROOT = Path(__file__).parent\nROOT = custom\nspec("pkg.target", ROOT / "target.py")',
    'spec("pkg.target", Path(__file__).parents[index] / "target.py")',
    'spec("pkg.target", Path(__file__).parents[999] / "target.py")',
    'spec("pkg.target", Path(__file__).parents[True] / "target.py")',
    'spec("pkg.target", Path(__file__).resolve(strict=dynamic) / "target.py")',
])
def test_unknown_file_locations_never_become_label_edges(tmp_path: Path, body: str) -> None:
    result = _file_scan(tmp_path, "from pathlib import Path\n"
                        "from importlib.util import spec_from_file_location as spec\n" + body + "\n")

    assert result["parse_errors"] == []
    assert result["explicit_hard_file_cycles"] == []
    assert len(result["unresolved_dynamic_imports"]) == 1
    assert "spec_from_file_location" in result["unresolved_dynamic_imports"][0]["expression"]


@pytest.mark.parametrize("rel,line,target", [
    ("tests/gate_meta/test_frozen_bundle_contract.py", 198, "core.services.scheduler._frozen_import_anchor"),
    ("tests/workbench/test_pending_build_sources.py", 22, "scripts.workbench.build"),
    ("tests/workbench/test_process_readiness.py", 133, "core.services.workbench.resource_readiness"),
])
def test_known_round1_sources_resolve_without_executing_or_editing_them(rel: str, line: int, target: str) -> None:
    roots = scan_import_cycles.PROD_ROOTS + scan_import_cycles.TEST_ROOTS
    file_to_mod, mod_to_file = scan_import_cycles._index_modules(roots, str(REPO_ROOT))
    source = str(REPO_ROOT / rel)
    edges = {kind: defaultdict(list) for kind in scan_import_cycles.KINDS}
    explicit = {kind: defaultdict(list) for kind in scan_import_cycles.KINDS}
    directories = {kind: defaultdict(list) for kind in scan_import_cycles.KINDS}
    unresolved: List[dict] = []
    parents: List[dict] = []

    scan_import_cycles._collect_module_edges(
        source, file_to_mod[source], ast.parse(Path(source).read_text(encoding="utf-8")),
        file_to_mod, mod_to_file, edges, explicit, directories, unresolved, parents, str(REPO_ROOT),
    )

    assert target in mod_to_file
    assert (rel, line) in explicit["lazy"][(file_to_mod[source], target)]
    assert not any(row["line"] == line for row in unresolved)
    if target == "scripts.workbench.build":
        assert not parents


def test_file_resolution_is_not_offered_without_a_scan_path_index() -> None:
    source = 'import importlib.util\nimportlib.util.spec_from_file_location("pkg.target", "/tmp/target.py")'
    resolved, unresolved = dyn_imports(ast.parse(source))
    assert resolved == []
    assert unresolved == [("hard", 2, "spec_from_file_location('pkg.target')")]


def test_source_path_lookup_does_not_guess_module_names() -> None:
    assert import_cycle_graph.source_file_target("/tmp/alias.py", {"/tmp/real.py": "pkg.real"}) is None

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Tuple

from tests._support.paths import REPO_ROOT

CALLGRAPH_SCRIPTS = REPO_ROOT / ".codestable" / "checkup" / "scripts"
CALLGRAPH_EXTRACT = CALLGRAPH_SCRIPTS / "callgraph_extract.py"


def _load_callgraph_extract() -> ModuleType:
    scripts = str(CALLGRAPH_SCRIPTS)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("test_callgraph_extract", CALLGRAPH_EXTRACT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_sources(sources: Dict[str, str]) -> Tuple[ModuleType, List[Dict[str, object]]]:
    module = _load_callgraph_extract()
    all_functions: Dict[str, Dict[str, object]] = {}
    names: Dict[str, List[str]] = defaultdict(list)
    file_functions: Dict[str, List[Dict[str, object]]] = {}
    file_imports: Dict[str, Dict[str, str]] = {}
    for rel, source in sources.items():
        tree = ast.parse(source)
        functions, imports = module._collect(tree, rel)
        file_functions[rel] = functions
        file_imports[rel] = imports
        for info in functions:
            qual = str(info["qual"])
            all_functions[qual] = info
            names[str(info["name"])].append(qual)
    edges, _dynamic, _dataflow = module._resolve_edges(
        all_functions,
        names,
        file_functions,
        file_imports,
    )
    return module, edges


def _resolve_source(source: str) -> Tuple[ModuleType, List[Dict[str, object]]]:
    return _resolve_sources({"sample.py": source})


def _confident_targets(edges: List[Dict[str, object]], source: str) -> Dict[str, str]:
    return {
        str(edge["to"]): str(edge["kind"])
        for edge in edges
        if edge["from"] == source and not edge["ambiguous"]
    }


def test_typed_receiver_inference_module_is_removed() -> None:
    module = _load_callgraph_extract()

    assert not (CALLGRAPH_SCRIPTS / "callgraph_type_index.py").exists()
    assert not hasattr(module, "_cti")
    assert not hasattr(module, "_merge_typed")


def test_imported_bare_alias_resolves_to_declared_source_not_global_same_name() -> None:
    _module, edges = _resolve_sources(
        {
            "helpers.py": "def actual():\n    return None\n",
            "other.py": "def renamed():\n    return None\n",
            "main.py": "from helpers import actual as renamed\ndef run():\n    return renamed()\n",
        }
    )

    targets = _confident_targets(edges, "main.py::run")
    assert targets["helpers.py::actual"] == "import"
    assert "other.py::renamed" not in targets


def test_function_local_import_alias_resolves_to_declared_source() -> None:
    _module, edges = _resolve_sources(
        {
            "helpers.py": "def actual():\n    return None\n",
            "other.py": "def renamed():\n    return None\n",
            "main.py": "def run():\n    from helpers import actual as renamed\n    return renamed()\n",
        }
    )

    targets = _confident_targets(edges, "main.py::run")
    assert targets["helpers.py::actual"] == "import"
    assert "other.py::renamed" not in targets


def test_imported_module_attribute_remains_confident_direct_syntax() -> None:
    _module, edges = _resolve_sources({
        "helpers.py": "def actual():\n    return None\n",
        "main.py": "import helpers as helper_module\ndef run():\n    return helper_module.actual()\n",
    })

    assert _confident_targets(edges, "main.py::run")["helpers.py::actual"] == "module_import_attr"


def test_nested_callable_has_own_node_and_calls_are_not_charged_to_outer() -> None:
    _module, edges = _resolve_source(
        """
def sink():
    return None

def outer():
    def inner():
        return sink()
    return inner()
"""
    )

    outer = _confident_targets(edges, "sample.py::outer")
    inner_qual = "sample.py::outer.<locals>.inner"
    assert outer[inner_qual] == "local"
    assert "sample.py::sink" not in outer
    assert _confident_targets(edges, inner_qual)["sample.py::sink"] == "local"


def test_nested_lambda_has_own_node_and_does_not_leak_calls_to_outer() -> None:
    _module, edges = _resolve_source(
        """
def sink():
    return None

def outer():
    transform = lambda: sink()
    return transform
"""
    )

    lambda_edges = [
        edge
        for edge in edges
        if edge["from"] == "sample.py::outer" and edge["kind"] == "lambda_definition"
    ]
    assert len(lambda_edges) == 1
    lambda_qual = str(lambda_edges[0]["to"])
    assert lambda_edges[0]["ambiguous"] is True
    assert "sample.py::sink" not in _confident_targets(edges, "sample.py::outer")
    assert _confident_targets(edges, lambda_qual)["sample.py::sink"] == "local"


def test_receiver_text_keeps_direct_nested_variable_and_factory_receivers_distinct() -> None:
    module = _load_callgraph_extract()
    tree = ast.parse(
        """
def probe(self, repo, factory):
    self.get()
    self.repo.get()
    repo.get()
    factory().get()
"""
    )
    function = tree.body[0]

    _bare, attrs, _dynamic, _module_attrs = module._callsites.collect_calls(function)

    assert attrs == {
        ("self", "get", 3),
        ("self.repo", "get", 4),
        ("repo", "get", 5),
        ("factory()", "get", 6),
    }


def test_same_receiver_calls_on_different_lines_remain_distinct_call_sites() -> None:
    module = _load_callgraph_extract()
    tree = ast.parse("def probe(repo):\n    repo.get()\n    repo.get()\n")

    _bare, attrs, _dynamic, _module_attrs = module._callsites.collect_calls(tree.body[0])

    assert attrs == {("repo", "get", 2), ("repo", "get", 3)}


def test_non_self_attribute_receivers_remain_ambiguous_even_with_type_hints() -> None:
    _module, edges = _resolve_source(
        """
class Repository:
    def get(self):
        return None
    def create(self):
        return None

class Snapshot:
    def to_dict(self):
        return {}

class Service:
    def __init__(self):
        self.repo = Repository()
        self.batch_repo = Repository()
    def get(self):
        return None
    def create(self):
        return None
    def to_dict(self):
        return {}
    def inspect(self, snapshot: Snapshot, repo: Repository):
        self.repo.get()
        self.batch_repo.create()
        snapshot.to_dict()
        repo.get()
"""
    )

    targets = _confident_targets(edges, "sample.py::Service.inspect")

    assert "sample.py::Repository.get" not in targets
    assert "sample.py::Repository.create" not in targets
    assert "sample.py::Snapshot.to_dict" not in targets
    assert "sample.py::Service.get" not in targets
    assert "sample.py::Service.create" not in targets
    assert "sample.py::Service.to_dict" not in targets
    ambiguous_targets = {
        str(edge["to"])
        for edge in edges
        if edge["from"] == "sample.py::Service.inspect" and edge["ambiguous"]
    }
    assert {
        "sample.py::Repository.get",
        "sample.py::Repository.create",
        "sample.py::Snapshot.to_dict",
    } <= ambiguous_targets


def test_for_target_rebinding_cannot_create_a_typed_confident_cycle() -> None:
    _module, edges = _resolve_source(
        """
class Repository:
    def get(self, service: Service):
        return service.inspect(self, ())

class Service:
    def inspect(self, repo: Repository, items):
        for repo in items:
            pass
        return repo.get(self)
"""
    )

    repository_targets = _confident_targets(edges, "sample.py::Repository.get")
    service_targets = _confident_targets(edges, "sample.py::Service.inspect")
    assert "sample.py::Service.inspect" not in repository_targets
    assert "sample.py::Repository.get" not in service_targets


def test_same_file_classes_with_same_method_names_only_link_direct_self_to_own_class() -> None:
    _module, edges = _resolve_source(
        """
class Alpha:
    def get(self):
        return None
    def run(self):
        return self.get()

class Beta:
    def get(self):
        return None
    def run(self):
        return self.get()
"""
    )

    alpha = _confident_targets(edges, "sample.py::Alpha.run")
    beta = _confident_targets(edges, "sample.py::Beta.run")
    assert alpha == {"sample.py::Alpha.get": "self"}
    assert beta == {"sample.py::Beta.get": "self"}


def test_untyped_factory_receiver_never_becomes_confident_current_class_edge() -> None:
    _module, edges = _resolve_source(
        """
def factory():
    return object()

class Service:
    def get(self):
        return None
    def inspect(self):
        return factory().get()
"""
    )

    assert "sample.py::Service.get" not in _confident_targets(edges, "sample.py::Service.inspect")
    assert any(
        edge["from"] == "sample.py::Service.inspect"
        and edge["to"] == "sample.py::Service.get"
        and edge["ambiguous"]
        for edge in edges
    )


def test_parse_file_reports_io_decode_and_syntax_errors(tmp_path: Path) -> None:
    module = _load_callgraph_extract()
    invalid_utf8 = tmp_path / "invalid_utf8.py"
    invalid_syntax = tmp_path / "invalid_syntax.py"
    invalid_utf8.write_bytes(b"VALUE = '\xff'\n")
    invalid_syntax.write_text("def broken(:\n", encoding="utf-8")
    cases = [
        (tmp_path / "missing.py", "missing.py"),
        (invalid_utf8, "invalid_utf8.py"),
        (invalid_syntax, "invalid_syntax.py"),
    ]

    errors = []
    for path, rel in cases:
        tree, error = module._parse_file(str(path), rel)
        assert tree is None
        assert rel in error
        errors.append(error)
    assert "codec can't decode" in errors[1]
    assert "invalid syntax" in errors[2]
    try:
        module._raise_parse_errors(errors)
    except RuntimeError as exc:
        assert "不能产出可信调用图" in str(exc)
    else:
        raise AssertionError("parse errors must block trusted callgraph output")


def test_full_callgraph_removes_known_false_cycles_and_keeps_real_recursive_mechanisms(tmp_path: Path) -> None:
    out_dir = tmp_path / "callgraph"
    env = os.environ.copy()
    env["CHECKUP_CALLGRAPH"] = str(out_dir)
    subprocess.run(
        [sys.executable, str(CALLGRAPH_EXTRACT)],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    cycles = json.loads((out_dir / "cycles.json").read_text(encoding="utf-8"))
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    edge_rows = json.loads((out_dir / "edges.json").read_text(encoding="utf-8"))
    confident_edges = {
        (edge["from"], edge["to"]): edge["kind"]
        for edge in edge_rows
        if not edge["ambiguous"]
    }
    assert confident_edges[
        (
            "core/infrastructure/migration_runner.py::run_migration",
            "core/infrastructure/migrations/__init__.py::run_migration",
        )
    ] == "import"
    cycle_sets = {frozenset(cycle) for cycle in cycles}

    known_false = {
        frozenset(
            {
                f"core/services/{path}.py::{class_name}._get_or_raise",
                f"core/services/{path}.py::{class_name}.get",
            }
        )
        for path, class_name in (
            ("equipment/machine_service", "MachineService"),
            ("personnel/operator_service", "OperatorService"),
            ("personnel/resource_team_service", "ResourceTeamService"),
            ("process/op_type_service", "OpTypeService"),
            ("process/part_service", "PartService"),
            ("process/supplier_service", "SupplierService"),
            ("scheduler/batch_service", "BatchService"),
        )
    }
    known_false.update(
        {
            frozenset(
                {
                    "core/services/personnel/operator_service.py::OperatorService._validate_operator_fields",
                    "core/services/personnel/operator_service.py::OperatorService.get",
                }
            ),
            frozenset(
                {
                    "core/services/scheduler/batch_service.py::BatchService.create",
                    "core/services/scheduler/batch_service.py::BatchService.create_no_tx",
                }
            ),
            frozenset(
                {
                    "core/services/scheduler/batch_service.py::BatchService.update",
                    "core/services/scheduler/batch_service.py::BatchService.update_no_tx",
                }
            ),
            frozenset(
                {
                    "core/services/scheduler/config/config_page_outcome.py::ConfigPageSaveOutcome.to_dict",
                    "core/services/scheduler/config/config_page_outcome.py::ConfigPageSaveOutcome.to_effective_snapshot_dict",
                }
            ),
            frozenset(
                {
                    "core/services/scheduler/schedule_plan_query_service.py::SchedulePlanQueryService.get_plan_time_span",
                    "core/services/scheduler/schedule_plan_query_service.py::SchedulePlanQueryService.get_plan_time_span_for_resolution",
                }
            ),
        }
    )
    assert known_false.isdisjoint(cycle_sets)

    required_real = {
        frozenset(
            {
                "core/services/common/excel_audit.py::_public_export_filter_value",
                "core/services/common/excel_audit.py::public_export_filters",
            }
        ),
        frozenset(
            {
                "core/services/scheduler/config/config_page_outcome.py::public_active_preset_reason",
                "core/services/scheduler/config/config_page_outcome.py::public_adjusted_reason_label",
            }
        ),
        frozenset(
            {
                "core/services/scheduler/summary/graph_public_summary.py::_project_public_graph_dict",
                "core/services/scheduler/summary/graph_public_summary.py::_project_public_graph_value",
            }
        ),
        frozenset(
            {
                "core/services/scheduler/summary/graph_public_summary.py::_project_public_graph_sequence",
                "core/services/scheduler/summary/graph_public_summary.py::_project_public_graph_value",
            }
        ),
        frozenset(
            {
                "tools/import_cycle_analysis.py::_classify_body",
                "tools/import_cycle_analysis.py::_classify_statement",
            }
        ),
        frozenset(
            {
                "tools/symbol_locator/render.py::_render_whereis_at",
                "tools/symbol_locator/render.py::render_whereis",
            }
        ),
    }
    assert required_real <= cycle_sets
    assert summary["typed_edges"] == 0
    assert not any(edge["kind"] == "typed" for edge in edge_rows)
    assert summary["graph_metrics"]["cycle_count"] == len(cycles)
    assert "simple cycles" in summary["graph_metrics"]["cycle_count_semantics"]

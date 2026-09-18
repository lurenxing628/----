"""FE-04 shared ownership, explicit adapters and cold-import dependency gates."""

import ast
import json
import os
import subprocess
import sys

import pytest

from tests._support.dependency_boundaries import assert_import_orders, assert_no_import_prefixes
from tests._support.paths import REPO_ROOT

_ADAPTERS = (
    ("core.services.workbench.process_quota_protection", "core.services.process.quota_protection",
     ("ProcessQuotaProtection", "quota_skip", "quota_skip_summary")),
    ("core.services.workbench.template_lineage", "core.services.scheduler.template_lineage",
     ("TemplateLineageWriter",)),
    ("core.services.workbench.template_lineage_query", "core.services.scheduler.template_lineage_query",
     ("TemplateLineageQuery", "validate_origin")),
)
_ENTRIES = (
    "core.services.process.quota_protection",
    "core.services.process.part_service",
    "core.services.scheduler.batch_copy",
    "core.services.scheduler.batch_template_ops",
    "core.services.scheduler.template_lineage",
    "core.services.scheduler.template_lineage_query",
)
_PROCESS_EXPORTS = {
    "OpTypeService", "SupplierService", "PartService",
    "RouteParser", "ParseResult", "ParseStatus", "DeletionValidator",
    "DeletionCheckResult", "ValidationResult",
}


def _run(script):
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=str(REPO_ROOT),
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("adapter,owner,names", _ADAPTERS)
def test_adapters_reexport_the_same_objects_in_both_cold_import_orders(adapter, owner, names):
    assert_import_orders(adapter, owner, names)


@pytest.mark.parametrize("module", _ENTRIES)
def test_shared_and_legacy_entries_never_load_the_workbench_service_facade(module):
    assert_no_import_prefixes(REPO_ROOT / (module.replace(".", "/") + ".py"),
                              ("core.services.workbench",))
    _run("import sys\nimport " + module + "\n"
         "assert not [name for name in sys.modules if name == 'core.services.workbench' "
         "or name.startswith('core.services.workbench.')]\n")


def test_process_package_is_lightweight_without_dynamic_export_fallbacks():
    tree = ast.parse((REPO_ROOT / "core/services/process/__init__.py").read_text(encoding="utf-8"))
    assert all(isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
               and isinstance(node.value.value, str) for node in tree.body)
    _run("import sys\nimport core.services.process\n"
         "assert not [name for name in sys.modules if name.startswith('core.services.process.')]\n")


def test_all_former_process_exports_remain_available_at_explicit_module_paths():
    _run("from core.services.process.deletion_validator import "
         "DeletionCheckResult, DeletionValidator, ValidationResult\n"
         "from core.services.process.op_type_service import OpTypeService\n"
         "from core.services.process.part_service import PartService\n"
         "from core.services.process.route_parser import ParseResult, ParseStatus, RouteParser\n"
         "from core.services.process.supplier_service import SupplierService\n"
         "assert all(callable(globals()[name]) for name in " + repr(sorted(_PROCESS_EXPORTS)) + ")\n")


def test_repository_consumers_do_not_import_removed_package_level_symbols():
    violations = []
    for folder in ("core", "data", "web", "scripts", "plugins", "tests"):
        for path in sorted((REPO_ROOT / folder).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "core.services.process":
                    names = {alias.name for alias in node.names}
                    if names & (_PROCESS_EXPORTS | {"*"}):
                        violations.append((str(path.relative_to(REPO_ROOT)), node.lineno, sorted(names)))
    assert not violations, violations


def test_real_import_scanner_has_no_fe04_package_or_service_cycles():
    completed = subprocess.run(
        [sys.executable, "-m", "tools.scan_import_cycles", "--json"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert not report["parse_errors"]
    members = {"core/services/process", "core/services/scheduler", "core/services/workbench"}
    assert not [row for row in report["hard_dir_cycles"] if members & set(row["members"])]
    assert not [row for row in report["hard_file_cycles"] if "core.services.process" in row]

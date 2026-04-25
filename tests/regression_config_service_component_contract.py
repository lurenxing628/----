from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = REPO_ROOT / "core/services/scheduler/config"
_SERVICE_COMMON_NEUTRAL_HELPERS = (
    "core.services.common.compat_parse",
    "core.services.common.degradation",
    "core.services.common.field_parse",
    "core.services.common.number_utils",
    "core.services.common.strict_parse",
    "core.services.common.value_policies",
)


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    module_parts = list(path.relative_to(REPO_ROOT).with_suffix("").parts)
    package_parts = module_parts[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = package_parts[: max(0, len(package_parts) - node.level + 1)]
                if node.module:
                    base_import = ".".join(base_parts + node.module.split("."))
                    imports.add(base_import)
                    imports.update(f"{base_import}.{alias.name}" for alias in node.names)
                else:
                    imports.update(".".join(base_parts + [alias.name]) for alias in node.names)
            elif node.module:
                imports.add(node.module)
                imports.update(f"{node.module}.{alias.name}" for alias in node.names)
    return imports


def _run_import_probe(module_name: str, *, attr_name: str | None = None) -> dict[str, bool]:
    probe = """
import importlib
import json
import sys

module_name = sys.argv[1]
attr_name = sys.argv[2] or None
module = importlib.import_module(module_name)
if attr_name:
    getattr(module, attr_name)
loaded = set(sys.modules)
print(json.dumps({
    "config_service": "core.services.scheduler.config.config_service" in loaded,
    "data_repositories": "data.repositories" in loaded,
    "batch_repo": "data.repositories.batch_repo" in loaded,
    "schedule_repo": "data.repositories.schedule_repo" in loaded,
    "greedy": "core.algorithms.greedy" in loaded,
}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", probe, module_name, attr_name or ""],
        cwd=str(REPO_ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _module_path_for_import(imported: str) -> Path | None:
    parts = str(imported or "").split(".")
    for end in range(len(parts), 0, -1):
        candidate = REPO_ROOT.joinpath(*parts[:end]).with_suffix(".py")
        if candidate.exists():
            return candidate
        package_init = REPO_ROOT.joinpath(*parts[:end], "__init__.py")
        if package_init.exists():
            return package_init
    return None


def _scheduler_local_imports(path: Path) -> list[Path]:
    targets: list[Path] = []
    for imported in sorted(_module_imports(path)):
        if not (imported == "core.services.scheduler" or imported.startswith("core.services.scheduler.")):
            continue
        target = _module_path_for_import(imported)
        if target is not None and target.exists():
            targets.append(target)
    return targets


def _scheduler_run_reachable_files() -> list[Path]:
    pending = list(sorted((REPO_ROOT / "core/services/scheduler/run").glob("*.py")))
    seen: set[Path] = set()
    ordered: list[Path] = []
    while pending:
        path = pending.pop(0)
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
        pending.extend(target for target in _scheduler_local_imports(path) if target not in seen)
    return ordered


def test_config_package_import_is_lazy() -> None:
    loaded = _run_import_probe("core.services.scheduler.config")

    assert loaded == {
        "config_service": False,
        "data_repositories": False,
        "batch_repo": False,
        "schedule_repo": False,
        "greedy": False,
    }


def test_scheduler_facade_config_service_import_is_lazy_to_unrelated_repositories() -> None:
    loaded = _run_import_probe("core.services.scheduler", attr_name="ConfigService")

    assert loaded["config_service"] is True
    assert loaded["batch_repo"] is False
    assert loaded["schedule_repo"] is False
    assert loaded["greedy"] is False


def test_repository_leaf_import_does_not_load_all_repositories() -> None:
    loaded = _run_import_probe("data.repositories.config_repo")

    assert loaded["batch_repo"] is False
    assert loaded["schedule_repo"] is False


def test_config_split_has_no_owner_backref_or_svc_proxy() -> None:
    violations: list[str] = []
    for path in sorted(CONFIG_ROOT.glob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for needle in ("owner: Any", "svc: Any", "ConfigPresetService(self)", "_display_state_reader", "set_display_state_reader"):
            if needle in text:
                violations.append(f"{rel}:{needle}")

    assert violations == []


def test_config_service_does_not_inject_facade_bound_methods_into_components() -> None:
    text = (CONFIG_ROOT / "config_service.py").read_text(encoding="utf-8")
    assert "default_snapshot_factory=self." not in text
    assert "ensure_defaults_if_pristine=self." not in text
    assert "ensure_defaults=self." not in text


def test_config_components_do_not_import_facade() -> None:
    violations: list[str] = []
    for path in sorted(CONFIG_ROOT.glob("*.py")):
        if path.name in {"__init__.py", "config_service.py"}:
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "core.services.scheduler.config":
                continue
            imported_names = {alias.name for alias in node.names}
            if "ConfigService" in imported_names or "config_service" in imported_names:
                violations.append(f"{rel}:{node.module}:{','.join(sorted(imported_names))}")
        for imported in sorted(_module_imports(path)):
            if imported == "core.services.scheduler.config.config_service":
                violations.append(f"{rel}:{imported}")

    assert violations == []


def test_config_pure_leaves_do_not_import_repositories_web_or_algorithms() -> None:
    pure_leaf_names = {
        "active_preset_provenance.py",
        "config_field_spec.py",
        "config_page_outcome.py",
        "config_page_write_plan.py",
        "config_snapshot.py",
        "config_validator.py",
        "config_weight_policy.py",
    }
    forbidden_prefixes = (
        "core.services.scheduler.config.config_service",
        "core.services.scheduler.degradation_messages",
        "data.repositories",
        "core.infrastructure.transaction",
        "flask",
        "web",
        "core.algorithms",
    )
    violations: list[str] = []
    for filename in sorted(pure_leaf_names):
        path = CONFIG_ROOT / filename
        for imported in sorted(_module_imports(path)):
            if imported.startswith(forbidden_prefixes):
                violations.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{imported}")

    assert violations == []


def test_page_save_service_keeps_provenance_as_typed_state() -> None:
    text = (CONFIG_ROOT / "config_page_save_service.py").read_text(encoding="utf-8")

    assert "provenance_state: Dict[str, Any]" not in text
    assert "provenance_state.get(" not in text


def test_current_config_display_state_is_not_a_dict_shell() -> None:
    from core.services.scheduler.config.active_preset_state import CurrentConfigDisplayState

    expected_fields = {
        "state",
        "status_label",
        "label",
        "baseline_key",
        "baseline_label",
        "baseline_source",
        "is_custom",
        "is_builtin",
        "degraded",
        "provenance_missing",
        "active_preset_missing",
        "active_preset_reason_missing",
        "reason",
        "baseline_probe_failed",
        "baseline_diff_fields",
        "repair_notices",
        "repair_notice",
    }

    assert {field.name for field in fields(CurrentConfigDisplayState)} == expected_fields
    state = CurrentConfigDisplayState(
        state="exact",
        status_label="与方案一致",
        label="当前运行配置与默认方案一致。",
        baseline_key="default",
        baseline_label="默认方案",
        baseline_source="builtin",
        is_custom=False,
        is_builtin=True,
        degraded=False,
        provenance_missing=False,
        active_preset_missing=False,
        active_preset_reason_missing=False,
        reason="",
        baseline_probe_failed=False,
    )
    assert set(state.to_legacy_dict()) == expected_fields

    text = (CONFIG_ROOT / "active_preset_state.py").read_text(encoding="utf-8")
    assert "payload: Dict[str, Any]" not in text
    assert "self.payload.get(" not in text


def test_active_preset_rows_distinguish_missing_row_from_blank_value() -> None:
    from core.services.scheduler.config.active_preset_service import ActivePresetService
    from core.services.scheduler.config.config_constants import ACTIVE_PRESET_KEY, ACTIVE_PRESET_REASON_KEY

    service = ActivePresetService(uow=object())
    missing_state = service.provenance_state_from_rows({})
    blank_state = service.provenance_state_from_rows(
        {
            ACTIVE_PRESET_KEY: SimpleNamespace(config_value=" "),
            ACTIVE_PRESET_REASON_KEY: SimpleNamespace(config_value="手动选择"),
        }
    )

    assert missing_state.active_missing is True
    assert missing_state.completeness_status == "missing_active_row"
    assert blank_state.active_missing is False
    assert blank_state.completeness_status == "active_blank"


def test_page_save_provenance_state_is_not_rehydrated_from_legacy_dict() -> None:
    text = (CONFIG_ROOT / "config_read_service.py").read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(CONFIG_ROOT / "config_read_service.py"))
    target = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "get_page_save_provenance_state"
    )
    source = ast.get_source_segment(text, target) or ""

    assert "display_state_from_rows" not in source
    assert "preset_state.get(" not in source


def test_algorithm_domain_does_not_import_scheduler_services_directly() -> None:
    violations: list[str] = []
    for path in sorted((REPO_ROOT / "core/algorithms").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        for imported in sorted(_module_imports(path)):
            if imported.startswith("core.services.scheduler"):
                violations.append(f"{rel}:{imported}")

    assert violations == []


def test_algorithm_domain_does_not_import_service_common() -> None:
    violations: list[str] = []
    for path in sorted((REPO_ROOT / "core/algorithms").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        for imported in sorted(_module_imports(path)):
            if imported == "core.services" or imported.startswith("core.services.common"):
                violations.append(f"{rel}:{imported}")

    assert violations == []


def test_runtime_config_projection_matches_service_field_contract() -> None:
    from core.models.schedule_config_runtime import list_runtime_config_fields
    from core.services.scheduler.config.config_field_spec import list_config_fields

    runtime_specs = {spec.key: spec for spec in list_runtime_config_fields()}
    service_specs = {spec.key: spec for spec in list_config_fields()}

    assert list(runtime_specs) == list(service_specs)
    for key, service_spec in service_specs.items():
        runtime_spec = runtime_specs[key]
        assert runtime_spec.field_type == service_spec.field_type
        assert runtime_spec.default == service_spec.default
        assert runtime_spec.min_value == service_spec.min_value
        assert runtime_spec.min_inclusive == service_spec.min_inclusive
        assert runtime_spec.choices == service_spec.choices


def test_runtime_config_projection_is_scheduler_config_neutral() -> None:
    violations: list[str] = []
    for path in sorted((REPO_ROOT / "core/models").glob("schedule_config_runtime*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        violations.extend(
            f"{rel}:{imported}"
            for imported in sorted(_module_imports(path))
            if imported.startswith("core.services")
        )

    assert violations == []


def test_scheduler_run_uses_shared_parse_and_degradation_helpers() -> None:
    violations: list[str] = []
    for path in _scheduler_run_reachable_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        for imported in sorted(_module_imports(path)):
            if imported == "core.services" or imported.startswith(_SERVICE_COMMON_NEUTRAL_HELPERS):
                violations.append(f"{rel}:{imported}")

    assert violations == []


def test_shared_layer_imports_no_services_data_web_or_algorithms() -> None:
    shared_root = REPO_ROOT / "core/shared"
    violations: list[str] = []
    if shared_root.exists():
        for path in sorted(shared_root.rglob("*.py")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            for imported in sorted(_module_imports(path)):
                forbidden_roots = ("core.services", "data", "web", "core.algorithms")
                if any(imported == root or imported.startswith(f"{root}.") for root in forbidden_roots):
                    violations.append(f"{rel}:{imported}")

    assert violations == []


def test_services_common_degradation_reexports_shared_identity() -> None:
    from core.services.common import degradation as service_degradation
    from core.shared import degradation as shared_degradation

    assert service_degradation.DegradationCollector is shared_degradation.DegradationCollector
    assert service_degradation.DegradationEvent is shared_degradation.DegradationEvent
    assert service_degradation.STABLE_DEGRADATION_CODES is shared_degradation.STABLE_DEGRADATION_CODES
    assert service_degradation.degradation_event_to_dict is shared_degradation.degradation_event_to_dict
    assert service_degradation.degradation_events_to_dicts is shared_degradation.degradation_events_to_dicts
    assert set(service_degradation.__all__) == {
        "STABLE_DEGRADATION_CODES",
        "DegradationCollector",
        "DegradationEvent",
        "degradation_event_to_dict",
        "degradation_events_to_dicts",
    }


def test_services_common_value_policies_reexports_shared_identity() -> None:
    from core.services.common import value_policies as service_value_policies
    from core.shared import value_policies as shared_value_policies

    assert service_value_policies.FieldPolicy is shared_value_policies.FieldPolicy
    assert service_value_policies.FIELD_POLICIES_BY_FIELD is shared_value_policies.FIELD_POLICIES_BY_FIELD
    assert service_value_policies.get_field_policy("priority_weight") is shared_value_policies.get_field_policy("priority_weight")


def test_services_common_parse_core_reexports_shared_identity() -> None:
    from core.services.common import compat_parse as service_compat_parse
    from core.services.common import strict_parse as service_strict_parse
    from core.shared import compat_parse as shared_compat_parse
    from core.shared import strict_parse as shared_strict_parse

    assert service_strict_parse.parse_required_float is shared_strict_parse.parse_required_float
    assert service_strict_parse.parse_optional_datetime is shared_strict_parse.parse_optional_datetime
    assert service_compat_parse.parse_compat_float is shared_compat_parse.parse_compat_float
    assert service_compat_parse.parse_compat_date is shared_compat_parse.parse_compat_date


def test_web_layer_uses_config_facade_instead_of_config_leaves() -> None:
    violations: list[str] = []
    for path in sorted((REPO_ROOT / "web").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        for imported in sorted(_module_imports(path)):
            if imported.startswith("core.services.scheduler.config.config_"):
                violations.append(f"{rel}:{imported}")

    assert violations == []

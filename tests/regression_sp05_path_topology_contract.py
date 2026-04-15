from __future__ import annotations

import ast
import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_STRONG_COMPAT_MODULES = {
    "core.services.scheduler.schedule_optimizer": "core.services.scheduler.run.schedule_optimizer",
    "core.services.scheduler.schedule_optimizer_steps": "core.services.scheduler.run.schedule_optimizer_steps",
}

SERVICE_BEHAVIOR_COMPAT_SYMBOLS = {
    "core.services.scheduler.config_service": "core.services.scheduler.config.config_service",
    "core.services.scheduler.config_snapshot": "core.services.scheduler.config.config_snapshot",
    "core.services.scheduler.config_validator": "core.services.scheduler.config.config_validator",
    "core.services.scheduler.freeze_window": "core.services.scheduler.run.freeze_window",
    "core.services.scheduler.schedule_input_builder": "core.services.scheduler.run.schedule_input_builder",
    "core.services.scheduler.schedule_input_collector": "core.services.scheduler.run.schedule_input_collector",
    "core.services.scheduler.schedule_orchestrator": "core.services.scheduler.run.schedule_orchestrator",
    "core.services.scheduler.schedule_persistence": "core.services.scheduler.run.schedule_persistence",
    "core.services.scheduler.schedule_summary": "core.services.scheduler.summary.schedule_summary",
    "core.services.scheduler.schedule_summary_types": "core.services.scheduler.summary.schedule_summary_types",
}

SERVICE_BEHAVIOR_COMPAT_PUBLIC_SYMBOLS = {
    "core.services.scheduler.config_service": ("ConfigService",),
    "core.services.scheduler.config_snapshot": (
        "ScheduleConfigSnapshot",
        "build_schedule_config_snapshot",
    ),
    "core.services.scheduler.config_validator": ("normalize_preset_snapshot",),
    "core.services.scheduler.freeze_window": ("build_freeze_window_seed",),
    "core.services.scheduler.schedule_input_builder": ("build_algo_operations",),
    "core.services.scheduler.schedule_input_collector": (
        "ScheduleRunInput",
        "collect_schedule_run_input",
    ),
    "core.services.scheduler.schedule_orchestrator": (
        "ScheduleOrchestrationOutcome",
        "orchestrate_schedule_run",
    ),
    "core.services.scheduler.schedule_persistence": (
        "has_actionable_schedule_rows",
        "persist_schedule",
    ),
    "core.services.scheduler.schedule_summary": (
        "SUMMARY_SIZE_LIMIT_BYTES",
        "apply_summary_size_guard",
        "build_overdue_items",
        "build_result_summary",
        "due_exclusive",
    ),
    "core.services.scheduler.schedule_summary_types": ("SummaryBuildContext",),
}

SERVICE_ROOTS_WITHOUT_COMPAT = (
    "core/services/scheduler/config_presets.py",
    "core/services/scheduler/schedule_input_contracts.py",
    "core/services/scheduler/schedule_input_runtime_support.py",
    "core/services/scheduler/schedule_template_lookup.py",
    "core/services/scheduler/schedule_summary_assembly.py",
    "core/services/scheduler/schedule_summary_degradation.py",
    "core/services/scheduler/schedule_summary_freeze.py",
)

ROUTE_COMPAT_MODULES = {
    "web.routes.scheduler_analysis": "web.routes.domains.scheduler.scheduler_analysis",
    "web.routes.scheduler_batch_detail": "web.routes.domains.scheduler.scheduler_batch_detail",
    "web.routes.scheduler_batches": "web.routes.domains.scheduler.scheduler_batches",
    "web.routes.scheduler_config": "web.routes.domains.scheduler.scheduler_config",
    "web.routes.scheduler_excel_calendar": "web.routes.domains.scheduler.scheduler_excel_calendar",
    "web.routes.scheduler_ops": "web.routes.domains.scheduler.scheduler_ops",
    "web.routes.scheduler_run": "web.routes.domains.scheduler.scheduler_run",
    "web.routes.scheduler_week_plan": "web.routes.domains.scheduler.scheduler_week_plan",
}

ROUTE_BEHAVIOR_COMPAT_SYMBOLS = {
    "web.routes.scheduler_excel_batches": "web.routes.domains.scheduler.scheduler_excel_batches",
}

ROUTE_BEHAVIOR_COMPAT_PUBLIC_SYMBOLS = {
    "web.routes.scheduler_excel_batches": (
        "_batch_baseline_extra_state",
        "_build_parts_cache",
        "_build_template_ops_snapshot",
        "bp",
        "excel_batches_confirm",
        "excel_batches_export",
        "excel_batches_page",
        "excel_batches_preview",
        "excel_batches_template",
    ),
}

ROUTE_ROOTS_REMOVED = (
    "web/routes/scheduler_bp.py",
    "web/routes/scheduler_calendar_pages.py",
    "web/routes/scheduler_excel_batches_baseline.py",
    "web/routes/scheduler_gantt.py",
    "web/routes/scheduler_pages.py",
    "web/routes/scheduler_resource_dispatch.py",
    "web/routes/scheduler_utils.py",
)

SCHEDULER_REAL_ROUTE_FILES = (
    "scheduler_analysis.py",
    "scheduler_batch_detail.py",
    "scheduler_batches.py",
    "scheduler_bp.py",
    "scheduler_calendar_pages.py",
    "scheduler_config.py",
    "scheduler_excel_batches.py",
    "scheduler_excel_batches_baseline.py",
    "scheduler_excel_calendar.py",
    "scheduler_gantt.py",
    "scheduler_ops.py",
    "scheduler_pages.py",
    "scheduler_resource_dispatch.py",
    "scheduler_run.py",
    "scheduler_utils.py",
    "scheduler_week_plan.py",
)


def _assert_init_has_no_imports(path: Path) -> None:
    module_ast = ast.parse(path.read_text(encoding="utf-8"))
    imports = [node for node in module_ast.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert imports == []


def test_sp05_service_topology_and_strong_compatibility() -> None:
    for package_name in ("config", "run", "summary", "batch", "dispatch", "gantt", "calendar"):
        package_dir = REPO_ROOT / "core/services/scheduler" / package_name
        assert package_dir.is_dir()
        assert (package_dir / "__init__.py").is_file()

    for delayed_package in ("batch", "dispatch", "gantt", "calendar"):
        _assert_init_has_no_imports(REPO_ROOT / "core/services/scheduler" / delayed_package / "__init__.py")

    lingering_root_files = [path for path in SERVICE_ROOTS_WITHOUT_COMPAT if (REPO_ROOT / path).exists()]
    assert lingering_root_files == []

    for old_name, new_name in SERVICE_STRONG_COMPAT_MODULES.items():
        new_path = REPO_ROOT / (new_name.replace(".", "/") + ".py")
        assert new_path.is_file(), new_path
        old_module = importlib.import_module(old_name)
        new_module = importlib.import_module(new_name)
        assert old_module is new_module, f"{old_name} must be a strong alias of {new_name}"

    for old_name, new_name in SERVICE_BEHAVIOR_COMPAT_SYMBOLS.items():
        new_path = REPO_ROOT / (new_name.replace(".", "/") + ".py")
        assert new_path.is_file(), new_path
        old_module = importlib.import_module(old_name)
        new_module = importlib.import_module(new_name)
        for symbol in SERVICE_BEHAVIOR_COMPAT_PUBLIC_SYMBOLS[old_name]:
            assert getattr(old_module, symbol) is getattr(new_module, symbol), f"{old_name}:{symbol}"


def test_sp05_route_topology_and_compatibility_matrix() -> None:
    for domain_name in ("scheduler", "process", "personnel", "equipment", "system"):
        domain_dir = REPO_ROOT / "web/routes/domains" / domain_name
        assert domain_dir.is_dir()
        assert (domain_dir / "__init__.py").is_file()

    for empty_domain in ("process", "personnel", "equipment", "system"):
        _assert_init_has_no_imports(REPO_ROOT / "web/routes/domains" / empty_domain / "__init__.py")

    scheduler_domain = REPO_ROOT / "web/routes/domains/scheduler"
    missing_real_files = [name for name in SCHEDULER_REAL_ROUTE_FILES if not (scheduler_domain / name).is_file()]
    assert missing_real_files == []

    lingering_root_files = [path for path in ROUTE_ROOTS_REMOVED if (REPO_ROOT / path).exists()]
    assert lingering_root_files == []

    root_domain_hijacks: list[str] = []
    for root_name in ("process.py", "personnel.py", "equipment.py", "system.py"):
        root_path = REPO_ROOT / "web/routes" / root_name
        if not root_path.exists():
            continue
        text = root_path.read_text(encoding="utf-8")
        for domain_name in ("process", "personnel", "equipment", "system"):
            needle = f".domains.{domain_name}"
            if needle in text:
                root_domain_hijacks.append(f"{root_path.relative_to(REPO_ROOT).as_posix()}:{needle}")
    assert root_domain_hijacks == []

    for old_name, new_name in ROUTE_COMPAT_MODULES.items():
        old_module = importlib.import_module(old_name)
        new_module = importlib.import_module(new_name)
        assert old_module is new_module, f"{old_name} must be a strong alias of {new_name}"

    for old_name, new_name in ROUTE_BEHAVIOR_COMPAT_SYMBOLS.items():
        old_module = importlib.import_module(old_name)
        new_module = importlib.import_module(new_name)
        assert old_module is not new_module, f"{old_name} is behavior-compatible, not a patch alias"
        for symbol in ROUTE_BEHAVIOR_COMPAT_PUBLIC_SYMBOLS[old_name]:
            assert getattr(old_module, symbol) is getattr(new_module, symbol), f"{old_name}:{symbol}"

    root_entrypoint = ast.parse((REPO_ROOT / "web/routes/scheduler.py").read_text(encoding="utf-8"))
    root_import_modules = {
        node.module
        for node in root_entrypoint.body
        if isinstance(node, ast.ImportFrom) and node.level == 1
    }
    assert root_import_modules == {"domains.scheduler", "domains.scheduler.scheduler_bp"}

    scheduler_pages = ast.parse(
        (REPO_ROOT / "web/routes/domains/scheduler/scheduler_pages.py").read_text(encoding="utf-8")
    )
    page_side_effect_imports = {
        alias.name
        for node in scheduler_pages.body
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None
        for alias in node.names
    }
    assert page_side_effect_imports == {
        "scheduler_analysis",
        "scheduler_batch_detail",
        "scheduler_batches",
        "scheduler_calendar_pages",
        "scheduler_config",
        "scheduler_excel_batches",
        "scheduler_excel_calendar",
        "scheduler_gantt",
        "scheduler_ops",
        "scheduler_resource_dispatch",
        "scheduler_run",
        "scheduler_week_plan",
    }


def test_sp05_safe_next_url_has_one_policy_module() -> None:
    navigation_utils = importlib.import_module("web.routes.navigation_utils")
    system_utils = importlib.import_module("web.routes.system_utils")
    assert hasattr(navigation_utils, "_safe_next_url_core")
    assert system_utils._safe_next_url("/scheduler/config") == "/scheduler/config"

    consumers = (
        REPO_ROOT / "web/routes/domains/scheduler/scheduler_batches.py",
        REPO_ROOT / "web/routes/domains/scheduler/scheduler_config.py",
        REPO_ROOT / "web/routes/system_ui_mode.py",
    )
    for path in consumers:
        source = path.read_text(encoding="utf-8")
        assert "navigation_utils import _safe_next_url" in source
        assert "system_utils import _safe_next_url" not in source

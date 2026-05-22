from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PR7E_PYTHON_FILES = (
    "core/infrastructure/migration_state.py",
    "core/infrastructure/migrations/__init__.py",
    "core/infrastructure/migrations/v9.py",
    "core/infrastructure/migrations/v10.py",
    "core/infrastructure/migrations/v11.py",
    "core/models/schedule_config_runtime_coercion.py",
    "core/services/scheduler/config/config_field_coercion.py",
    "core/services/scheduler/config/config_field_spec.py",
    "core/services/scheduler/config/config_snapshot.py",
    "core/services/scheduler/config/config_constants.py",
    "core/services/scheduler/config/config_presets.py",
    "core/services/scheduler/config/config_validator.py",
    "core/models/schedule_config_runtime_fields.py",
    "core/models/schedule_config_runtime_snapshot.py",
    "core/services/scheduler/schedule_plan_query_service.py",
    "core/services/scheduler/schedule_service.py",
    "core/shared/field_labels.py",
    "core/services/scheduler/run/schedule_candidate_runner.py",
    "core/services/scheduler/run/schedule_candidate_selection.py",
    "core/services/scheduler/run/schedule_candidate_specs.py",
    "core/services/scheduler/run/schedule_graph_dispatch_context.py",
    "core/services/scheduler/run/schedule_input_collector.py",
    "core/services/scheduler/run/schedule_orchestrator.py",
    "core/services/scheduler/run/schedule_candidate_persistence_helpers.py",
    "core/services/scheduler/run/schedule_persistence.py",
    "core/services/scheduler/summary/schedule_summary_assembly.py",
    "data/repositories/schedule_candidate_repo.py",
    "web/routes/domains/scheduler/scheduler_analysis.py",
    "web/routes/domains/scheduler/scheduler_config.py",
    "web/routes/domains/scheduler/scheduler_config_display_state.py",
    "web/routes/domains/scheduler/scheduler_run.py",
    "web/routes/domains/scheduler/scheduler_week_plan.py",
    "web/viewmodels/page_manuals_scheduler_outputs.py",
    "web/viewmodels/scheduler_analysis_candidates.py",
    "web/viewmodels/scheduler_config_panel.py",
    "tests/regression_config_field_spec_contract.py",
    "tests/regression_graph_config_bootstrap_contract.py",
    "tests/regression_migrate_v9_graph_config_defaults.py",
    "tests/regression_scheduler_candidate_analysis_contract.py",
    "tests/regression_scheduler_candidate_config_contract.py",
    "tests/regression_scheduler_candidate_persistence_contract.py",
    "tests/regression_scheduler_candidate_py38_contract.py",
    "tests/regression_scheduler_candidate_schema_contract.py",
    "tests/regression_scheduler_candidate_summary_contract.py",
    "tests/regression_scheduler_candidate_performance_guard.py",
    "tests/regression_scheduler_config_route_contract.py",
    "tests/regression_scheduler_config_spec_sync_contract.py",
    "tests/regression_scheduler_graph_auto_selection_contract.py",
    "tests/regression_scheduler_graph_cycle_policy_contract.py",
    "tests/regression_scheduler_graph_on_mode_contract.py",
)

PR7E_FRONTEND_FILES = (
    "templates/scheduler/config.html",
    "web_new_test/templates/scheduler/config.html",
    "templates/scheduler/_run_panel.html",
    "templates/scheduler/analysis.html",
    "templates/scheduler/gantt.html",
    "web_new_test/templates/scheduler/gantt.html",
    "static/js/gantt.js",
    "static/js/gantt_adapter.js",
    "static/js/gantt_contract.js",
    "static/css/aps_gantt_simulation.css",
)

_PEP585_PART = r"\b(?:list|dict|set|tuple)\s*\["
_UNION_WITH_NONE_PART = r"(?:^|[^|])\|\s*" + "None" + r"|" + "None" + r"\s*\|"
_PY39_TYPE_HINT_RE = re.compile(_PEP585_PART + "|" + _UNION_WITH_NONE_PART)
_BANNED_IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+(sqlalchemy|psycopg|psycopg2|asyncpg|pymysql|requests)\b", re.M)


def test_pr7e_python_files_keep_python38_type_syntax() -> None:
    for rel_path in PR7E_PYTHON_FILES:
        source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        ast.parse(source, filename=rel_path)
        assert _PY39_TYPE_HINT_RE.search(source) is None, rel_path


def test_pr7e_does_not_add_heavy_drivers_or_external_frontend_resources() -> None:
    for rel_path in PR7E_PYTHON_FILES:
        source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        assert _BANNED_IMPORT_RE.search(source) is None, rel_path

    for rel_path in PR7E_FRONTEND_FILES:
        source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        assert "https://" not in source and "http://" not in source, rel_path
        assert "cdn" not in source.lower(), rel_path

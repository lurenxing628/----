"""Shared plan reads preserve object identity, resolver contracts and zero writes."""

import ast
import importlib

import pytest

from core.services.common import plan_identity as identity_owner
from core.services.common import plan_query as query_owner
from core.services.common.bounded_plan_query import _PagePlanQueryService
from core.services.common.plan_query import SchedulePlanQueryService
from core.services.scheduler import schedule_plan_identity_builder as identity_adapter
from core.services.scheduler import schedule_plan_query_service as query_adapter
from core.services.scheduler import workbench_plan_page
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository
from tests._support.dependency_boundaries import assert_import_orders, assert_no_import_prefixes
from tests._support.paths import REPO_ROOT
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.plan_catalog_support import candidate, history, seed_operation
from tests.workbench.plan_catalog_support import scenario as seed_scenario

VERSION = 7
_ALIASES = (
    ("core.services.scheduler.schedule_plan_query_service", "core.services.common.plan_query",
     ("SchedulePlanQueryService", "SchedulePlanResolution", "SchedulePlanRoleOption", "ROLE_ADOPTED",
      "ROLE_BASELINE_BEST", "ROLE_CRITICAL_BEST", "VALID_PLAN_ROLES", "plan_role_label", "_normalize_role")),
    ("core.services.scheduler.schedule_plan_identity_builder", "core.services.common.plan_identity",
     ("build_plan_identity", "latest_official_version")),
    ("core.services.scheduler.workbench_plan_page", "core.services.common.bounded_plan_query",
     ("_PagePlanQueryService",)),
)


@pytest.mark.parametrize("legacy,owner,names", _ALIASES)
def test_original_plan_paths_reexport_the_same_objects_in_both_cold_orders(legacy, owner, names):
    assert_import_orders(legacy, owner, names)


@pytest.mark.parametrize("adapter,owner", [(identity_adapter, identity_owner), (query_adapter, query_owner)])
def test_every_original_public_name_is_the_same_owner_object(adapter, owner):
    expected = {name for name in vars(owner) if not name.startswith("_")}
    assert {name for name in vars(adapter) if not name.startswith("_")} == expected
    assert all(getattr(adapter, name) is getattr(owner, name) for name in expected)


def test_page_retains_its_complete_original_public_surface():
    expected = {"DEFAULT_PLAN_PAGE_SIZE", "HistoryPlanPage", "MAX_PLAN_PAGE_SIZE", "Optional", "PlanCatalogEntry",
                "ROLE_ADOPTED", "ScenarioPlanPage", "ScheduleAdjustmentScenario", "SchedulePlanQueryService",
                "SchedulePlanResolution", "Tuple", "WorkbenchPlanCatalogRepository", "annotations",
                "build_history_plan_page", "build_plan_identity", "build_scenario_plan_page", "dataclass",
                "replace", "sqlite3", "validate_after_scenario_id", "validate_before_version", "validate_page_size"}
    assert {name for name in vars(workbench_plan_page) if not name.startswith("_")} == expected
    assert workbench_plan_page.SchedulePlanQueryService is query_owner.SchedulePlanQueryService
    assert workbench_plan_page.SchedulePlanResolution is query_owner.SchedulePlanResolution
    assert workbench_plan_page.build_plan_identity is identity_owner.build_plan_identity


def test_all_current_query_import_consumers_keep_their_original_exports():
    legacy = importlib.import_module("core.services.scheduler.schedule_plan_query_service")
    names = set()
    for directory in ("core", "data", "web", "tests", "plugins"):
        for path in (REPO_ROOT / directory).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("schedule_plan_query_service"):
                    names.update(alias.name for alias in node.names)
    assert "SchedulePlanResolution" in names and "plan_role_label" in names
    assert all(hasattr(legacy, name) for name in names), sorted(names)


@pytest.mark.parametrize("name", ["plan_identity", "plan_query", "bounded_plan_query"])
def test_shared_plan_layer_does_not_import_scheduler_workbench_or_report(name):
    path = REPO_ROOT / "core/services/common" / (name + ".py")
    assert_no_import_prefixes(path, ("core.services.scheduler", "core.services.workbench", "core.services.report"))
    source = path.read_text(encoding="utf-8")
    assert "TYPE_CHECKING" not in source and "import_module" not in source and "__import__" not in source


@pytest.mark.parametrize("bounded", [False, True])
def test_strict_permissive_scenario_and_history_reads_preserve_all_tables(schema_conn, bounded):
    conn = schema_conn
    op_id = seed_operation(conn)
    history(conn, VERSION - 1, op_id=op_id)
    history(conn, VERSION, op_id=op_id)
    candidate(conn, VERSION, "adopted", source="schedule", saved="no")
    candidate(conn, VERSION, "baseline_best", op_id=op_id)
    seed_scenario(conn, "scenario-plain", VERSION, op_id=op_id)
    conn.commit()
    try:
        before = all_rows(conn)
        changes = conn.total_changes
        conn.execute("PRAGMA query_only=ON")
        service = (_PagePlanQueryService(WorkbenchPlanCatalogRepository(conn), VERSION)
                   if bounded else SchedulePlanQueryService(conn))
        current = service.resolve_plan(VERSION, "adopted")
        assert current.plan_identity.can_write_feedback
        assert service.resolve_existing_plan(VERSION, "adopted") == current
        assert not service.resolve_plan(VERSION - 1, "adopted").plan_identity.can_write_feedback
        fallback = service.resolve_plan(VERSION, "critical_best")
        assert fallback.status == "fallback_to_adopted" and not fallback.plan_identity.can_write_feedback
        with pytest.raises(ValueError):
            service.resolve_existing_plan(VERSION, "critical_best")
        scenario = service.resolve_plan_view(VERSION, "adopted", "scenario-plain")
        assert scenario.is_scenario_preview and not scenario.plan_identity.can_write_feedback
        assert service.resolve_existing_plan(VERSION, "baseline_best").source_table == "candidate_rows"
        for resolution in (current, scenario):
            assert service.list_plan_detail_rows_all_for_resolution(version=resolution.version,
                source_table=resolution.source_table, candidate_id=resolution.candidate_id,
                scenario_id=resolution.scenario_id)
        assert all_rows(conn) == before and conn.total_changes == changes
    finally:
        conn.close()

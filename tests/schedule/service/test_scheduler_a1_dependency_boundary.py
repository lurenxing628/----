"""刻画 scheduler A1 解耦的兼容路径、对象 identity、签名和导入边界。"""

import json
import os
import subprocess
import sys
from inspect import signature
from pathlib import Path

from core.models import scheduler_degradation_messages as degradation_leaf
from core.services.scheduler import degradation_messages as degradation_compat
from core.services.scheduler import execution_fact_provider as fact_compat
from core.services.scheduler import execution_snapshot as snapshot_compat
from core.services.scheduler import number_utils as number_compat
from core.services.scheduler import operation_execution_scope_read as scope_compat
from core.services.scheduler import resource_dispatch_execution_enrichment as enrichment_compat
from core.services.scheduler.contracts import graph_public_summary as graph_leaf
from core.services.scheduler.contracts import optimizer_public_safety as safety_leaf
from core.services.scheduler.contracts import optimizer_public_search_report as search_leaf
from core.services.scheduler.contracts import schedule_summary_types as types_leaf
from core.services.scheduler.contracts import summary_count_parse as count_leaf
from core.services.scheduler.execution import execution_fact_provider as fact_leaf
from core.services.scheduler.execution import execution_snapshot as snapshot_leaf
from core.services.scheduler.execution import operation_execution_scope_read as scope_leaf
from core.services.scheduler.execution import resource_dispatch_execution_enrichment as enrichment_leaf
from core.services.scheduler.summary import graph_public_summary as graph_compat
from core.services.scheduler.summary import optimizer_public_safety as safety_compat
from core.services.scheduler.summary import optimizer_public_search_report as search_compat
from core.services.scheduler.summary import schedule_summary_types as types_compat
from core.services.scheduler.summary import summary_count_parse as count_compat
from core.shared import boolean_normalize as boolean_leaf
from core.shared import number_utils as shared_number

_ROOT = Path(__file__).resolve().parents[3]
_A1_MEMBERS = {
    "core/services/scheduler",
    "core/services/scheduler/config",
    "core/services/scheduler/run",
    "core/services/scheduler/summary",
}
_MODULES = (
    "core.shared.boolean_normalize",
    "core.models.scheduler_degradation_messages",
    "core.services.scheduler.execution.execution_fact_provider",
    "core.services.scheduler.execution.execution_snapshot",
    "core.services.scheduler.execution.operation_execution_scope_read",
    "core.services.scheduler.execution.resource_dispatch_execution_enrichment",
    "core.services.scheduler.contracts.graph_public_summary",
    "core.services.scheduler.contracts.optimizer_public_safety",
    "core.services.scheduler.contracts.optimizer_public_search_report",
    "core.services.scheduler.contracts.schedule_summary_types",
    "core.services.scheduler.contracts.summary_count_parse",
    "core.services.scheduler.number_utils",
    "core.services.scheduler.degradation_messages",
    "core.services.scheduler.execution_fact_provider",
    "core.services.scheduler.execution_snapshot",
    "core.services.scheduler.operation_execution_scope_read",
    "core.services.scheduler.resource_dispatch_execution_enrichment",
    "core.services.scheduler.summary.graph_public_summary",
    "core.services.scheduler.summary.optimizer_public_safety",
    "core.services.scheduler.summary.optimizer_public_search_report",
    "core.services.scheduler.summary.schedule_summary_types",
    "core.services.scheduler.summary.summary_count_parse",
)


def _assert_same_exports(compat_module, leaf_module, names) -> None:
    for name in names:
        assert getattr(compat_module, name) is getattr(leaf_module, name), name


def test_old_paths_are_one_way_identity_compatible_with_new_leaves() -> None:
    _assert_same_exports(number_compat, boolean_leaf, ("to_yes_no",))
    _assert_same_exports(number_compat, shared_number, ("parse_finite_float", "parse_finite_int"))
    _assert_same_exports(degradation_compat, degradation_leaf, degradation_compat.__all__)

    _assert_same_exports(fact_compat, fact_leaf, fact_compat.__all__)
    _assert_same_exports(snapshot_compat, snapshot_leaf, snapshot_compat.__all__)
    _assert_same_exports(scope_compat, scope_leaf, scope_compat.__all__)
    _assert_same_exports(
        enrichment_compat,
        enrichment_leaf,
        ("apply_execution_state_to_row", "execution_exception_labels", "row_op_id"),
    )

    _assert_same_exports(graph_compat, graph_leaf, graph_compat.__all__)
    _assert_same_exports(safety_compat, safety_leaf, safety_compat.__all__)
    _assert_same_exports(search_compat, search_leaf, search_compat.__all__)
    _assert_same_exports(
        types_compat,
        types_leaf,
        (
            "AlgorithmSummaryState",
            "DEFAULT_TRUNCATION_TIERS",
            "FallbackState",
            "FreezeState",
            "RuntimeState",
            "ScheduleResultStatus",
            "SummaryBuildContext",
            "TruncationTier",
            "WarningState",
        ),
    )
    _assert_same_exports(count_compat, count_leaf, ("_meta_bool_state", "parse_summary_count"))


def test_key_public_signatures_stay_frozen() -> None:
    expected = {
        boolean_leaf.to_yes_no: "(value: 'Any', *, default: 'str' = 'no') -> 'str'",
        snapshot_leaf.build_execution_snapshot: (
            "(facts_by_op_id: 'Dict[int, ExecutionFact]', op_ids: 'Sequence[int]') -> 'ExecutionSnapshot'"
        ),
        snapshot_leaf.collect_execution_snapshot_for_plan_rows: (
            "(conn, rows: 'Sequence[Any]', plan_fields: 'Mapping[str, Any]', *, "
            "op_ids: 'Sequence[int]', logger=None) -> 'ExecutionSnapshot'"
        ),
        scope_leaf.scope_from_plan_row: "(row: 'Any', plan_fields: 'Mapping[str, Any]') -> 'OperationExecutionScope'",
        graph_leaf.project_public_graph_analysis: "(value: 'Any') -> 'Dict[str, Any]'",
        search_leaf.project_search_report: "(value: 'Any') -> 'Tuple[Dict[str, Any], Dict[str, Any]]'",
        count_leaf.parse_summary_count: "(value: 'Any', *, field: 'str') -> 'Tuple[int, Optional[str]]'",
    }
    assert {func: str(signature(func)) for func in expected} == expected


def test_old_and_new_modules_import_in_both_orders_in_clean_interpreters() -> None:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for module_names in (_MODULES, tuple(reversed(_MODULES))):
        code = "import importlib\n" + "\n".join(
            f"importlib.import_module({module_name!r})" for module_name in module_names
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr


def test_a1_hard_directory_scc_is_absent() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "tools.scan_import_cycles", "--json"],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(completed.stdout)
    cycles = [set(item["members"]) for item in report["hard_dir_cycles"]]
    remaining = [members for members in cycles if members & _A1_MEMBERS]
    assert not remaining, remaining

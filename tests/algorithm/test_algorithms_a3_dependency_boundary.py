"""A3 依赖解耦边界：冻结根 API、旧路径 identity、导入顺序、模块状态与 SCC 终态。"""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ROOT_INIT = _REPO_ROOT / "core" / "algorithms" / "__init__.py"
_ROOT_INIT_SHA256 = "bca5f1d3515eb3f8ab694e0003e7dcce01fa4abe88584da906fabd2814e3594b"
_A3_DIR_MEMBERS = {
    "core/algorithms",
    "core/algorithms/greedy",
    "core/algorithms/greedy/dispatch",
}
_REMAINING_PRODUCTION_DIR_CYCLES = {
    (".", "web/bootstrap", "web/routes", "web/routes/domains/scheduler"): 41,
    ("core/plugins", "core/services/common"): 2,
    ("core/services/report", "core/services/report/exporters"): 3,
}
_REMAINING_WITH_TESTS_DIR_CYCLES = {
    **_REMAINING_PRODUCTION_DIR_CYCLES,
    ("tests/gantt", "tests/operation_execution", "tests/resource_dispatch", "tests/web_pages"): 11,
}
_A3_PARENT_AWARE_FILE_MEMBERS = {
    "core.algorithms",
    "core.algorithms.greedy",
    "core.algorithms.greedy.dispatch",
    "core.algorithms.greedy.dispatch.sgs",
    "core.algorithms.greedy.dispatch.sgs_graph",
    "core.algorithms.greedy.dispatch.sgs_scoring",
    "core.algorithms.greedy.run_context",
    "core.algorithms.greedy.scheduler",
}

_AUTO_ASSIGN_CONTRACT_NAMES = (
    "AUTO_ASSIGN_REASON_SUCCESS",
    "AUTO_ASSIGN_REASON_MISSING_OP_TYPE_ID",
    "AUTO_ASSIGN_REASON_MISSING_MACHINE_POOL",
    "AUTO_ASSIGN_REASON_NO_MACHINE_CANDIDATE",
    "AUTO_ASSIGN_REASON_NO_OPERATOR_CANDIDATE",
    "AUTO_ASSIGN_REASON_NO_FEASIBLE_PAIR",
    "AUTO_ASSIGN_REASON_INVALID_INTERNAL_HOURS",
    "AutoAssignAttempt",
    "auto_assign_attempt_from_result",
)
_ALGO_STATS_CONTRACT_NAMES = (
    "_BUCKETS",
    "_COUNTER_BUCKETS",
    "_SAMPLE_BUCKETS",
    "_empty_stats",
    "_strict_int",
    "ensure_algo_stats",
    "increment_counter",
    "make_algo_stats",
)


def _public_names(module):
    return tuple(module.__all__)


def _assert_same_objects(old_module, canonical_module) -> None:
    for name in _public_names(old_module):
        assert getattr(old_module, name) is getattr(canonical_module, name), (
            old_module.__name__,
            canonical_module.__name__,
            name,
        )


def _run_import_cycle_scan(*, include_tests: bool):
    command = [sys.executable, "-m", "tools.scan_import_cycles", "--json"]
    if include_tests:
        command.append("--include-tests")
    completed = subprocess.run(
        command,
        cwd=str(_REPO_ROOT),
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _dir_cycle_map(payload):
    return {tuple(record["members"]): len(record["edges"]) for record in payload["hard_dir_cycles"]}


def test_root_greedy_scheduler_public_contract_is_unchanged() -> None:
    from core.algorithms import GreedyScheduler as RootGreedyScheduler
    from core.algorithms import __all__ as root_exports
    from core.algorithms.greedy import GreedyScheduler as GreedyPackageScheduler
    from core.algorithms.greedy.scheduler import GreedyScheduler as CanonicalGreedyScheduler

    assert hashlib.sha256(_ROOT_INIT.read_bytes()).hexdigest() == _ROOT_INIT_SHA256
    assert RootGreedyScheduler is GreedyPackageScheduler is CanonicalGreedyScheduler
    assert RootGreedyScheduler.__module__ == "core.algorithms.greedy.scheduler"
    assert tuple(root_exports) == (
        "SortStrategy",
        "StrategyFactory",
        "BatchForSort",
        "GreedyScheduler",
        "ScheduleResult",
        "ScheduleSummary",
    )
    assert str(inspect.signature(RootGreedyScheduler)) == (
        "(calendar_service, config_service=None, logger: 'Optional[logging.Logger]' = None)"
    )
    assert str(inspect.signature(RootGreedyScheduler.schedule)) == (
        "(self, operations: 'List[Any]', batches: 'Dict[str, Any]', strategy: 'Optional[SortStrategy]' = None, "
        "strategy_params: 'Optional[Dict[str, Any]]' = None, start_dt: 'Any' = None, end_date: 'Any' = None, "
        "machine_downtimes: 'Optional[Dict[str, List[Tuple[datetime, datetime]]]]' = None, "
        "batch_order_override: 'Optional[List[str]]' = None, seed_results: 'Optional[List[ScheduleResult]]' = None, "
        "dispatch_mode: 'Optional[str]' = None, dispatch_rule: 'Optional[str]' = None, "
        "resource_pool: 'Optional[Dict[str, Any]]' = None, readiness_gate_enabled: 'bool' = False, "
        "strict_mode: 'bool' = False, graph_ready_context: 'Optional[Any]' = None) -> "
        "'Tuple[List[ScheduleResult], ScheduleSummary, SortStrategy, Dict[str, Any]]'"
    )

    class DerivedScheduler(RootGreedyScheduler):
        pass

    assert DerivedScheduler.schedule is RootGreedyScheduler.schedule


def test_old_paths_reexport_the_canonical_contract_and_runtime_objects() -> None:
    import core.algorithm_contracts.date_parsers as canonical_date_parsers
    import core.algorithm_contracts.dispatch_rules as canonical_dispatch_rules
    import core.algorithm_contracts.ordering as canonical_ordering
    import core.algorithm_contracts.priority_constants as canonical_priority_constants
    import core.algorithm_contracts.sort_strategies as canonical_sort_strategies
    import core.algorithm_contracts.types as canonical_types
    import core.algorithm_contracts.value_domains as canonical_value_domains
    import core.algorithm_runtime.algo_stats as canonical_algo_stats
    import core.algorithm_runtime.auto_assign_contract as canonical_auto_assign
    import core.algorithm_runtime.downtime as canonical_downtime
    import core.algorithm_runtime.internal_slot as canonical_internal_slot
    import core.algorithm_runtime.run_state as canonical_run_state
    import core.algorithm_runtime.runtime_state as canonical_runtime_state
    import core.algorithms.dispatch_rules as old_dispatch_rules
    import core.algorithms.greedy.algo_stats as old_algo_stats
    import core.algorithms.greedy.auto_assign as old_auto_assign
    import core.algorithms.greedy.date_parsers as old_date_parsers
    import core.algorithms.greedy.dispatch.runtime_state as old_runtime_state
    import core.algorithms.greedy.downtime as old_downtime
    import core.algorithms.greedy.internal_slot as old_internal_slot
    import core.algorithms.greedy.run_state as old_run_state
    import core.algorithms.ordering as old_ordering
    import core.algorithms.priority_constants as old_priority_constants
    import core.algorithms.sort_strategies as old_sort_strategies
    import core.algorithms.types as old_types
    import core.algorithms.value_domains as old_value_domains

    compatibility_modules = (
        (old_date_parsers, canonical_date_parsers),
        (old_dispatch_rules, canonical_dispatch_rules),
        (old_ordering, canonical_ordering),
        (old_priority_constants, canonical_priority_constants),
        (old_sort_strategies, canonical_sort_strategies),
        (old_types, canonical_types),
        (old_value_domains, canonical_value_domains),
        (old_downtime, canonical_downtime),
        (old_internal_slot, canonical_internal_slot),
        (old_run_state, canonical_run_state),
        (old_runtime_state, canonical_runtime_state),
    )
    for old_module, canonical_module in compatibility_modules:
        _assert_same_objects(old_module, canonical_module)

    for name in _AUTO_ASSIGN_CONTRACT_NAMES:
        assert getattr(old_auto_assign, name) is getattr(canonical_auto_assign, name)
    for name in _ALGO_STATS_CONTRACT_NAMES:
        assert getattr(old_algo_stats, name) is getattr(canonical_algo_stats, name)


def test_canonical_objects_use_their_natural_module_names() -> None:
    from core.algorithm_contracts.sort_strategies import WeightedStrategy
    from core.algorithm_contracts.types import ScheduleSummary
    from core.algorithm_runtime.auto_assign_contract import AutoAssignAttempt
    from core.algorithm_runtime.internal_slot import InternalSlotEstimate
    from core.algorithm_runtime.run_state import ScheduleRunState

    assert WeightedStrategy.__module__ == "core.algorithm_contracts.sort_strategies"
    assert ScheduleSummary.__module__ == "core.algorithm_contracts.types"
    assert AutoAssignAttempt.__module__ == "core.algorithm_runtime.auto_assign_contract"
    assert InternalSlotEstimate.__module__ == "core.algorithm_runtime.internal_slot"
    assert ScheduleRunState.__module__ == "core.algorithm_runtime.run_state"


def test_new_leaf_roots_do_not_aggregate_exports_or_reverse_import() -> None:
    forbidden_prefixes = ("core.algorithms", "core.services")
    leaves = (
        _REPO_ROOT / "core" / "algorithm_contracts",
        _REPO_ROOT / "core" / "algorithm_runtime",
    )
    for leaf in leaves:
        init_tree = ast.parse((leaf / "__init__.py").read_text(encoding="utf-8"))
        meaningful_init_nodes = [
            node
            for node in init_tree.body
            if not (isinstance(node, ast.Expr) and isinstance(node.value, (ast.Str, ast.Constant)))
        ]
        assert meaningful_init_nodes == []

        for path in leaf.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imports.append(node.module)
            assert not any(name.startswith(forbidden_prefixes) for name in imports), (path, imports)


def test_old_first_and_canonical_first_imports_work_in_independent_python38_processes() -> None:
    script = r'''
import importlib
import sys

assert sys.version_info[:2] == (3, 8), sys.version
order = sys.argv[1]
pairs = (
    ("core.algorithms.greedy.date_parsers", "core.algorithm_contracts.date_parsers", ("parse_date", "parse_datetime", "due_exclusive")),
    ("core.algorithms.dispatch_rules", "core.algorithm_contracts.dispatch_rules", ("DispatchRule", "DispatchInputs", "build_dispatch_key")),
    ("core.algorithms.sort_strategies", "core.algorithm_contracts.sort_strategies", ("SortStrategy", "WeightedStrategy", "StrategyFactory")),
    ("core.algorithms.types", "core.algorithm_contracts.types", ("ScheduleResult", "ScheduleSummary")),
    ("core.algorithms.greedy.internal_slot", "core.algorithm_runtime.internal_slot", ("InternalSlotEstimate", "estimate_internal_slot")),
    ("core.algorithms.greedy.run_state", "core.algorithm_runtime.run_state", ("ScheduleRunState",)),
)
for old_name, canonical_name, names in pairs:
    first, second = (old_name, canonical_name) if order == "old-first" else (canonical_name, old_name)
    importlib.import_module(first)
    importlib.import_module(second)
    old_module = importlib.import_module(old_name)
    canonical_module = importlib.import_module(canonical_name)
    for name in names:
        assert getattr(old_module, name) is getattr(canonical_module, name), (old_name, canonical_name, name)
from core.algorithms import GreedyScheduler as root_scheduler
from core.algorithms.greedy import GreedyScheduler as package_scheduler
from core.algorithms.greedy.scheduler import GreedyScheduler as canonical_scheduler
assert root_scheduler is package_scheduler is canonical_scheduler
'''
    for order in ("old-first", "canonical-first"):
        subprocess.run(
            [sys.executable, "-c", script, order],
            cwd=str(_REPO_ROOT),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            check=True,
            capture_output=True,
            text=True,
        )


def test_old_algo_stats_deepcopy_patch_still_controls_snapshot(monkeypatch) -> None:
    import core.algorithms.greedy.algo_stats as stats_module

    calls = []

    def recording_deepcopy(value):
        calls.append(value)
        return {"patched": True}

    monkeypatch.setattr(stats_module, "deepcopy", recording_deepcopy)
    target = {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}

    assert stats_module.snapshot_algo_stats(target) == {"patched": True}
    assert calls == [target]


def test_a3_is_removed_without_changing_other_directory_cycles() -> None:
    production = _run_import_cycle_scan(include_tests=False)
    with_tests = _run_import_cycle_scan(include_tests=True)

    assert production["module_count"] == 779
    assert with_tests["module_count"] == 1475
    assert _dir_cycle_map(production) == _REMAINING_PRODUCTION_DIR_CYCLES
    assert _dir_cycle_map(with_tests) == _REMAINING_WITH_TESTS_DIR_CYCLES
    assert not any(_A3_DIR_MEMBERS == set(record["members"]) for record in production["hard_dir_cycles"])
    assert not any(_A3_DIR_MEMBERS == set(record["members"]) for record in with_tests["hard_dir_cycles"])

    for payload, unresolved_count in ((production, 6), (with_tests, 44)):
        assert payload["parse_errors"] == []
        assert len(payload["unresolved_dynamic_imports"]) == unresolved_count
        assert len(payload["hard_file_cycles"]) == 9
        assert len(payload["explicit_hard_file_cycles"]) == 0
        assert payload["runtime_file_cycle_count"] == 13
        assert len(payload["explicit_runtime_file_cycles"]) == 4
        assert not any(
            member in {"core/algorithm_contracts", "core/algorithm_runtime"}
            for record in payload["hard_dir_cycles"]
            for member in record["members"]
        )

    algorithm_file_records = [
        record
        for record in production["hard_file_cycle_records"]
        if set(record["members"]) == _A3_PARENT_AWARE_FILE_MEMBERS
    ]
    assert len(algorithm_file_records) == 1
    assert len(algorithm_file_records[0]["edges"]) == 24

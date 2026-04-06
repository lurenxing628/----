import os
import sqlite3
import sys

VALID_STRATEGIES = ("priority_first", "due_date_first", "weighted", "fifo")
VALID_DISPATCH_MODES = ("batch_order", "sgs")
VALID_DISPATCH_RULES = ("slack", "cr", "atc")
VALID_ALGO_MODES = ("greedy", "improve")
VALID_OBJECTIVES = ("min_overdue", "min_tardiness", "min_weighted_tardiness", "min_changeover")
VALID_STRATEGIES_MIXED = ("PRIORITY_FIRST", "due_date_first", "Weighted", "FIFO")
VALID_DISPATCH_MODES_MIXED = ("BATCH_ORDER", "Sgs")
VALID_DISPATCH_RULES_MIXED = ("SLACK", "Cr", "ATC")
VALID_ALGO_MODES_MIXED = ("GREEDY", "Improve")
VALID_OBJECTIVES_MIXED = ("MIN_OVERDUE", "min_tardiness", "MIN_WEIGHTED_TARDINESS", "Min_Changeover")


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def load_schema(conn: sqlite3.Connection, repo_root: str) -> None:
    with open(os.path.join(repo_root, "schema.sql"), "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


class FakeRepo:
    def __init__(self, values):
        self.values = dict(values or {})

    def get_value(self, key, default=None):
        return self.values.get(key, default)


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.scheduler.config_service import ConfigService
    from core.services.scheduler.config_snapshot import ScheduleConfigSnapshot, build_schedule_config_snapshot
    from core.services.scheduler.config_validator import normalize_preset_snapshot
    from web.viewmodels.scheduler_analysis_vm import _comparison_metric_from_algo, _objective_key_from_algo_objective

    assert _objective_key_from_algo_objective("MIN_WEIGHTED_TARDINESS") == "weighted_tardiness_hours"
    assert _comparison_metric_from_algo({"objective": "MIN_OVERDUE"}) == "overdue_count"
    assert (
        _comparison_metric_from_algo(
            {"objective": "MIN_WEIGHTED_TARDINESS", "comparison_metric": "weighted_tardiness_hours"}
        )
        == "weighted_tardiness_hours"
    )

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    load_schema(conn, repo_root)

    cfg = ConfigService(conn)
    cfg.ensure_defaults()
    cfg.set_objective("MIN_WEIGHTED_TARDINESS")
    snap = cfg.get_snapshot()
    raw = cfg.get("objective")
    assert snap.objective == "min_weighted_tardiness", f"配置快照未归一化 objective：{snap.objective!r}"
    assert raw == "min_weighted_tardiness", f"配置仓储未归一化 objective：{raw!r}"

    base = ScheduleConfigSnapshot(
        sort_strategy="priority_first",
        priority_weight=0.6,
        due_weight=0.3,
        ready_weight=0.1,
        holiday_default_efficiency=0.5,
        enforce_ready_default="yes",
        prefer_primary_skill="no",
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        auto_assign_enabled="yes",
        ortools_enabled="no",
        ortools_time_limit_seconds=5,
        algo_mode="greedy",
        time_budget_seconds=20,
        objective="min_overdue",
        freeze_window_enabled="no",
        freeze_window_days=0,
    )
    normalized = normalize_preset_snapshot(
        {
            "sort_strategy": " Weighted ",
            "dispatch_mode": " SGS ",
            "dispatch_rule": " CR ",
            "algo_mode": " IMPROVE ",
            "objective": " MIN_CHANGEOVER ",
        },
        base=base,
        valid_strategies=VALID_STRATEGIES,
        valid_dispatch_modes=VALID_DISPATCH_MODES,
        valid_dispatch_rules=VALID_DISPATCH_RULES,
        valid_algo_modes=VALID_ALGO_MODES,
        valid_objectives=VALID_OBJECTIVES,
    )
    assert normalized.sort_strategy == "weighted", f"preset sort_strategy 未归一化：{normalized.sort_strategy!r}"
    assert normalized.dispatch_mode == "sgs", f"preset dispatch_mode 未归一化：{normalized.dispatch_mode!r}"
    assert normalized.dispatch_rule == "cr", f"preset dispatch_rule 未归一化：{normalized.dispatch_rule!r}"
    assert normalized.algo_mode == "improve", f"preset algo_mode 未归一化：{normalized.algo_mode!r}"
    assert normalized.objective == "min_changeover", f"preset objective 未归一化：{normalized.objective!r}"

    normalized_mixed_valid = normalize_preset_snapshot(
        {
            "sort_strategy": " Weighted ",
            "dispatch_mode": " SGS ",
            "dispatch_rule": " CR ",
            "algo_mode": " IMPROVE ",
            "objective": " MIN_CHANGEOVER ",
        },
        base=base,
        valid_strategies=VALID_STRATEGIES_MIXED,
        valid_dispatch_modes=VALID_DISPATCH_MODES_MIXED,
        valid_dispatch_rules=VALID_DISPATCH_RULES_MIXED,
        valid_algo_modes=VALID_ALGO_MODES_MIXED,
        valid_objectives=VALID_OBJECTIVES_MIXED,
    )
    assert normalized_mixed_valid.sort_strategy == "weighted", (
        f"mixed valid preset sort_strategy 未归一化：{normalized_mixed_valid.sort_strategy!r}"
    )
    assert normalized_mixed_valid.dispatch_mode == "sgs", (
        f"mixed valid preset dispatch_mode 未归一化：{normalized_mixed_valid.dispatch_mode!r}"
    )
    assert normalized_mixed_valid.dispatch_rule == "cr", (
        f"mixed valid preset dispatch_rule 未归一化：{normalized_mixed_valid.dispatch_rule!r}"
    )
    assert normalized_mixed_valid.algo_mode == "improve", (
        f"mixed valid preset algo_mode 未归一化：{normalized_mixed_valid.algo_mode!r}"
    )
    assert normalized_mixed_valid.objective == "min_changeover", (
        f"mixed valid preset objective 未归一化：{normalized_mixed_valid.objective!r}"
    )

    defaults = {
        "sort_strategy": "priority_first",
        "priority_weight": 0.6,
        "due_weight": 0.3,
        "ready_weight": 0.1,
        "holiday_default_efficiency": 0.5,
        "enforce_ready_default": "yes",
        "prefer_primary_skill": "no",
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "auto_assign_enabled": "yes",
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 5,
        "algo_mode": "greedy",
        "time_budget_seconds": 20,
        "objective": "min_overdue",
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
    }
    dirty_repo = FakeRepo(
        {
            "sort_strategy": " Weighted ",
            "dispatch_mode": " SGS ",
            "dispatch_rule": " CR ",
            "algo_mode": " IMPROVE ",
            "objective": " MIN_WEIGHTED_TARDINESS ",
        }
    )
    dirty_snap = build_schedule_config_snapshot(
        dirty_repo,
        defaults=defaults,
        valid_strategies=VALID_STRATEGIES,
        valid_dispatch_modes=VALID_DISPATCH_MODES,
        valid_dispatch_rules=VALID_DISPATCH_RULES,
        valid_algo_modes=VALID_ALGO_MODES,
        valid_objectives=VALID_OBJECTIVES,
    )
    assert dirty_snap.sort_strategy == "weighted", f"脏 DB sort_strategy 未归一化：{dirty_snap.sort_strategy!r}"
    assert dirty_snap.dispatch_mode == "sgs", f"脏 DB dispatch_mode 未归一化：{dirty_snap.dispatch_mode!r}"
    assert dirty_snap.dispatch_rule == "cr", f"脏 DB dispatch_rule 未归一化：{dirty_snap.dispatch_rule!r}"
    assert dirty_snap.algo_mode == "improve", f"脏 DB algo_mode 未归一化：{dirty_snap.algo_mode!r}"
    assert dirty_snap.objective == "min_weighted_tardiness", f"脏 DB objective 未归一化：{dirty_snap.objective!r}"

    dirty_snap_mixed_valid = build_schedule_config_snapshot(
        dirty_repo,
        defaults=defaults,
        valid_strategies=VALID_STRATEGIES_MIXED,
        valid_dispatch_modes=VALID_DISPATCH_MODES_MIXED,
        valid_dispatch_rules=VALID_DISPATCH_RULES_MIXED,
        valid_algo_modes=VALID_ALGO_MODES_MIXED,
        valid_objectives=VALID_OBJECTIVES_MIXED,
    )
    assert dirty_snap_mixed_valid.sort_strategy == "weighted", (
        f"mixed valid 脏 DB sort_strategy 未归一化：{dirty_snap_mixed_valid.sort_strategy!r}"
    )
    assert dirty_snap_mixed_valid.dispatch_mode == "sgs", (
        f"mixed valid 脏 DB dispatch_mode 未归一化：{dirty_snap_mixed_valid.dispatch_mode!r}"
    )
    assert dirty_snap_mixed_valid.dispatch_rule == "cr", (
        f"mixed valid 脏 DB dispatch_rule 未归一化：{dirty_snap_mixed_valid.dispatch_rule!r}"
    )
    assert dirty_snap_mixed_valid.algo_mode == "improve", (
        f"mixed valid 脏 DB algo_mode 未归一化：{dirty_snap_mixed_valid.algo_mode!r}"
    )
    assert dirty_snap_mixed_valid.objective == "min_weighted_tardiness", (
        f"mixed valid 脏 DB objective 未归一化：{dirty_snap_mixed_valid.objective!r}"
    )

    conn.close()
    print("OK")


if __name__ == "__main__":
    main()

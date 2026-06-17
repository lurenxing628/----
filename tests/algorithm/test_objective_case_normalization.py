"""回归测试：排产策略类字段的大小写归一化贯穿全链路——set_objective 写入与读回都把 MIN_WEIGHTED_TARDINESS 归一为小写，normalize_preset_snapshot 与 build_schedule_config_snapshot 把脏 DB / preset 里带大小写和空格的 sort_strategy/dispatch_mode/dispatch_rule/algo_mode/objective 归一为标准小写值，且 viewmodel 的 objective_key/comparison_metric 能识别大写 objective。"""


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


class FakeRepo:
    def __init__(self, values):
        self.values = dict(values or {})

    def get_value(self, key, default=None):
        return self.values.get(key, default)


def test_objective_case_normalization(schema_conn) -> None:

    from core.services.scheduler.config.config_service import ConfigService
    from core.services.scheduler.config.config_snapshot import ScheduleConfigSnapshot, build_schedule_config_snapshot
    from core.services.scheduler.config.config_validator import normalize_preset_snapshot
    from web.viewmodels.scheduler_analysis_vm import _comparison_metric_from_algo, _objective_key_from_algo_objective

    assert _objective_key_from_algo_objective("MIN_WEIGHTED_TARDINESS") == "weighted_tardiness_hours"
    assert _comparison_metric_from_algo({"objective": "MIN_OVERDUE"}) == "overdue_count"
    assert (
        _comparison_metric_from_algo(
            {"objective": "MIN_WEIGHTED_TARDINESS", "comparison_metric": "weighted_tardiness_hours"}
        )
        == "weighted_tardiness_hours"
    )

    conn = schema_conn

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
        auto_assign_persist="yes",
        ortools_enabled="no",
        ortools_time_limit_seconds=5,
        algo_mode="greedy",
        time_budget_seconds=20,
        objective="min_overdue",
        freeze_window_enabled="no",
        freeze_window_days=0,
        graph_analysis_mode="off",
        graph_block_on_cycle="no",
        graph_critical_weight=500,
        graph_impact_weight=10,
        graph_debug_export="no",
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
        "auto_assign_persist": "yes",
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 5,
        "algo_mode": "greedy",
        "time_budget_seconds": 20,
        "objective": "min_overdue",
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
        "graph_analysis_mode": "off",
        "graph_block_on_cycle": "no",
        "graph_critical_weight": 500,
        "graph_impact_weight": 10,
        "graph_debug_export": "no",
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
    )
    assert dirty_snap.sort_strategy == "weighted", f"脏 DB sort_strategy 未归一化：{dirty_snap.sort_strategy!r}"
    assert dirty_snap.dispatch_mode == "sgs", f"脏 DB dispatch_mode 未归一化：{dirty_snap.dispatch_mode!r}"
    assert dirty_snap.dispatch_rule == "cr", f"脏 DB dispatch_rule 未归一化：{dirty_snap.dispatch_rule!r}"
    assert dirty_snap.algo_mode == "improve", f"脏 DB algo_mode 未归一化：{dirty_snap.algo_mode!r}"
    assert dirty_snap.objective == "min_weighted_tardiness", f"脏 DB objective 未归一化：{dirty_snap.objective!r}"

    dirty_snap_mixed_valid = build_schedule_config_snapshot(
        dirty_repo,
        defaults=defaults,
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

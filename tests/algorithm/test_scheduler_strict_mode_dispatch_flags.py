"""回归测试：strict_mode 下排产配置的 dispatch 相关字段须以正确 field 名抛 ValidationError——build_schedule_config_snapshot 对非法 dispatch_mode、normalize_preset_snapshot 对非法 dispatch_rule、resolve_schedule_params 对空白 sort_strategy/dispatch_mode/dispatch_rule/auto_assign_enabled 及非法 auto_assign_enabled、以及 ConfigService.get_snapshot(strict_mode=True) 对空白 dispatch_mode/auto_assign_enabled，都须报对应字段名。"""


class _StubRepo:
    def __init__(self, values):
        self._values = dict(values or {})

    def get_value(self, key, default=None):
        return self._values.get(key, default)


def _default_snapshot_kwargs():
    return {
        "sort_strategy": "priority_first",
        "priority_weight": 0.4,
        "due_weight": 0.5,
        "ready_weight": 0.1,
        "holiday_default_efficiency": 1.0,
        "enforce_ready_default": "yes",
        "prefer_primary_skill": "no",
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "auto_assign_enabled": "no",
        "auto_assign_persist": "yes",
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 10,
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


def _expect_validation(label, func, field):
    from core.infrastructure.errors import ValidationError

    try:
        func()
    except ValidationError as e:
        assert e.field == field, f"{label} 字段名异常：{e.field!r}"
        return
    raise AssertionError(f"{label} 应抛出 ValidationError(field={field!r})")


def test_scheduler_strict_mode_dispatch_flags(schema_conn) -> None:

    from core.algorithms.greedy.schedule_params import resolve_schedule_params
    from core.services.scheduler.config.config_service import ConfigService
    from core.services.scheduler.config.config_snapshot import ScheduleConfigSnapshot, build_schedule_config_snapshot
    from core.services.scheduler.config.config_validator import normalize_preset_snapshot

    defaults = _default_snapshot_kwargs()

    def _config_snapshot(**overrides):
        data = dict(defaults)
        data.update(overrides)
        return ScheduleConfigSnapshot(**data)

    _expect_validation(
        "config_snapshot.dispatch_mode",
        lambda: build_schedule_config_snapshot(
            _StubRepo({"dispatch_mode": "bad_mode"}),
            defaults=defaults,
            strict_mode=True,
        ),
        "dispatch_mode",
    )

    base = ScheduleConfigSnapshot(**defaults)
    _expect_validation(
        "config_validator.dispatch_rule",
        lambda: normalize_preset_snapshot(
            {"dispatch_rule": "bad_rule"},
            base=base,
            strict_mode=True,
        ),
        "dispatch_rule",
    )

    _expect_validation(
        "resolve_schedule_params.sort_strategy.blank",
        lambda: resolve_schedule_params(
            config=_config_snapshot(
                sort_strategy="   ",
                dispatch_mode="sgs",
                dispatch_rule="slack",
                auto_assign_enabled="no",
            ),
            strategy=None,
            strategy_params=None,
            start_dt=None,
            end_date=None,
            dispatch_mode=None,
            dispatch_rule=None,
            resource_pool={},
            strict_mode=True,
        ),
        "sort_strategy",
    )
    _expect_validation(
        "resolve_schedule_params.dispatch_mode.blank",
        lambda: resolve_schedule_params(
            config=_config_snapshot(
                sort_strategy="priority_first",
                dispatch_mode="   ",
                dispatch_rule="slack",
                auto_assign_enabled="no",
            ),
            strategy=None,
            strategy_params=None,
            start_dt=None,
            end_date=None,
            dispatch_mode=None,
            dispatch_rule=None,
            resource_pool={},
            strict_mode=True,
        ),
        "dispatch_mode",
    )
    _expect_validation(
        "resolve_schedule_params.dispatch_rule.blank",
        lambda: resolve_schedule_params(
            config=_config_snapshot(
                sort_strategy="priority_first",
                dispatch_mode="sgs",
                dispatch_rule="   ",
                auto_assign_enabled="no",
            ),
            strategy=None,
            strategy_params=None,
            start_dt=None,
            end_date=None,
            dispatch_mode=None,
            dispatch_rule=None,
            resource_pool={},
            strict_mode=True,
        ),
        "dispatch_rule",
    )
    _expect_validation(
        "resolve_schedule_params.auto_assign_enabled.blank",
        lambda: resolve_schedule_params(
            config=_config_snapshot(
                sort_strategy="priority_first",
                dispatch_mode="sgs",
                dispatch_rule="slack",
                auto_assign_enabled="   ",
            ),
            strategy=None,
            strategy_params=None,
            start_dt=None,
            end_date=None,
            dispatch_mode=None,
            dispatch_rule=None,
            resource_pool={},
            strict_mode=True,
        ),
        "auto_assign_enabled",
    )

    _expect_validation(
        "resolve_schedule_params.auto_assign_enabled",
        lambda: resolve_schedule_params(
            config=_config_snapshot(
                sort_strategy="priority_first",
                dispatch_mode="sgs",
                dispatch_rule="slack",
                auto_assign_enabled="maybe",
            ),
            strategy=None,
            strategy_params=None,
            start_dt=None,
            end_date=None,
            dispatch_mode=None,
            dispatch_rule=None,
            resource_pool={},
            strict_mode=True,
        ),
        "auto_assign_enabled",
    )

    conn = schema_conn

    try:
        cfg = ConfigService(conn, logger=None, op_logger=None)

        def _expect_snapshot_validation(key: str) -> None:
            cfg.restore_default()
            cfg.repo.set(key, "   ", description="regression-blank")
            cfg.get_snapshot(strict_mode=True)

        _expect_validation(
            "config_service.get_snapshot.dispatch_mode.blank",
            lambda: _expect_snapshot_validation("dispatch_mode"),
            "dispatch_mode",
        )
        _expect_validation(
            "config_service.get_snapshot.auto_assign_enabled.blank",
            lambda: _expect_snapshot_validation("auto_assign_enabled"),
            "auto_assign_enabled",
        )
    finally:
        conn.close()



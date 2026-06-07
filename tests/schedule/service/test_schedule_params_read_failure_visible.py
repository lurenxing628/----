"""守护 resolve_schedule_params 读配置失败可见性：读取 sort_strategy/priority_weight 等字段抛异常时，无论 strict_mode 与否都必须抛出 ValidationError 并带上对应字段名和中文标签(如"排产策略"/"优先级权重")，绝不静默 fallback 到默认值。"""


class _ExplodingConfig:
    @property
    def sort_strategy(self):
        raise RuntimeError("config access exploded: sort_strategy")


class _ExplodingWeightedConfig:
    sort_strategy = "weighted"
    dispatch_mode = "sgs"
    dispatch_rule = "slack"
    auto_assign_enabled = "no"

    @property
    def priority_weight(self):
        raise RuntimeError("config access exploded: priority_weight")


def _assert_visible_read_failure(
    resolve_schedule_params,
    ValidationError,
    *,
    config,
    strict_mode: bool,
    expected_field: str,
    expected_text: str,
) -> None:
    try:
        resolve_schedule_params(
            config=config,
            strategy=None,
            strategy_params=None,
            start_dt=None,
            end_date=None,
            dispatch_mode=None,
            dispatch_rule=None,
            resource_pool={},
            strict_mode=bool(strict_mode),
        )
    except ValidationError as exc:
        if exc.field != expected_field:
            raise RuntimeError(f"配置读取失败字段异常：{exc.field!r}")
        if expected_text not in str(exc.message):
            raise RuntimeError(f"配置读取失败未透出具体字段：{exc.message!r}")
    else:
        raise RuntimeError("配置读取失败后不应静默 fallback")


def test_schedule_params_read_failure_visible() -> None:

    from core.algorithms.greedy.schedule_params import resolve_schedule_params
    from core.infrastructure.errors import ValidationError

    _assert_visible_read_failure(
        resolve_schedule_params,
        ValidationError,
        config=_ExplodingConfig(),
        strict_mode=False,
        expected_field="sort_strategy",
        expected_text="排产策略",
    )
    _assert_visible_read_failure(
        resolve_schedule_params,
        ValidationError,
        config=_ExplodingConfig(),
        strict_mode=True,
        expected_field="sort_strategy",
        expected_text="排产策略",
    )
    _assert_visible_read_failure(
        resolve_schedule_params,
        ValidationError,
        config=_ExplodingWeightedConfig(),
        strict_mode=False,
        expected_field="priority_weight",
        expected_text="优先级权重",
    )
    _assert_visible_read_failure(
        resolve_schedule_params,
        ValidationError,
        config=_ExplodingWeightedConfig(),
        strict_mode=True,
        expected_field="priority_weight",
        expected_text="优先级权重",
    )



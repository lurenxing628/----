import os
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


class _ExplodingConfig:
    def get(self, key, default=None):
        raise RuntimeError(f"config access exploded: {key}")


class _ExplodingWeightedConfig:
    sort_strategy = "weighted"
    dispatch_mode = "sgs"
    dispatch_rule = "slack"
    auto_assign_enabled = "no"

    def get(self, key, default=None):
        raise RuntimeError(f"weighted config access exploded: {key}")



def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms.greedy.schedule_params import resolve_schedule_params
    from core.infrastructure.errors import ValidationError

    algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}
    params = resolve_schedule_params(
        config=_ExplodingConfig(),
        strategy=None,
        strategy_params=None,
        start_dt=None,
        end_date=None,
        dispatch_mode=None,
        dispatch_rule=None,
        resource_pool={},
        algo_stats=algo_stats,
        strict_mode=False,
    )

    if getattr(params.strategy, "value", None) != "priority_first":
        raise RuntimeError(f"读取失败后 sort_strategy 默认值异常：{params.strategy!r}")
    if params.dispatch_mode_key != "batch_order":
        raise RuntimeError(f"读取失败后 dispatch_mode 默认值异常：{params.dispatch_mode_key!r}")
    if getattr(params.dispatch_rule_enum, "value", None) != "slack":
        raise RuntimeError(f"读取失败后 dispatch_rule 默认值异常：{params.dispatch_rule_enum!r}")
    if params.auto_assign_enabled is not False:
        raise RuntimeError(f"读取失败后 auto_assign_enabled 默认值异常：{params.auto_assign_enabled!r}")
    if not params.warnings:
        raise RuntimeError("关键配置读取失败后不应静默返回默认值且 warnings=[]")

    warnings_text = "\n".join(str(item) for item in (params.warnings or []))
    for key in ("sort_strategy", "dispatch_mode", "dispatch_rule", "auto_assign_enabled"):
        if key not in warnings_text or "读取失败" not in warnings_text:
            raise RuntimeError(f"关键配置读取失败未出现在 warnings 中：key={key} warnings={params.warnings!r}")

    param_fallbacks = algo_stats.get("param_fallbacks") or {}
    for counter_key in (
        "sort_strategy_read_failed_count",
        "dispatch_mode_read_failed_count",
        "dispatch_rule_read_failed_count",
        "auto_assign_enabled_read_failed_count",
    ):
        if int(param_fallbacks.get(counter_key) or 0) != 1:
            raise RuntimeError(f"关键配置读取失败计数异常：{counter_key} -> {param_fallbacks!r}")

    try:
        resolve_schedule_params(
            config=_ExplodingConfig(),
            strategy=None,
            strategy_params=None,
            start_dt=None,
            end_date=None,
            dispatch_mode=None,
            dispatch_rule=None,
            resource_pool={},
            strict_mode=True,
        )
    except ValidationError as exc:
        if exc.field != "sort_strategy":
            raise RuntimeError(f"strict_mode 读取失败字段异常：{exc.field!r}")
        if "读取失败" not in exc.message:
            raise RuntimeError(f"strict_mode 读取失败未透出原因：{exc.message!r}")
    else:
        raise RuntimeError("strict_mode=True 时关键配置读取失败应直接抛出 ValidationError")

    weighted_stats = {"fallback_counts": {}, "param_fallbacks": {}}
    weighted_params = resolve_schedule_params(
        config=_ExplodingWeightedConfig(),
        strategy=None,
        strategy_params=None,
        start_dt=None,
        end_date=None,
        dispatch_mode=None,
        dispatch_rule=None,
        resource_pool={},
        algo_stats=weighted_stats,
        strict_mode=False,
    )

    if getattr(weighted_params.strategy, "value", None) != "weighted":
        raise RuntimeError(f"weighted 配置读取后策略异常：{weighted_params.strategy!r}")

    weighted_warnings = "\n".join(str(item) for item in (weighted_params.warnings or []))
    for key in ("priority_weight", "due_weight"):
        if key not in weighted_warnings or "读取失败" not in weighted_warnings:
            raise RuntimeError(f"weighted 读取失败未出现在 warnings 中：key={key} warnings={weighted_params.warnings!r}")

    weighted_fallbacks = weighted_stats.get("param_fallbacks") or {}
    for counter_key in ("weighted_priority_weight_defaulted_count", "weighted_due_weight_defaulted_count"):
        if int(weighted_fallbacks.get(counter_key) or 0) != 1:
            raise RuntimeError(f"weighted 默认计数异常：{counter_key} -> {weighted_fallbacks!r}")

    try:
        resolve_schedule_params(
            config=_ExplodingWeightedConfig(),
            strategy=None,
            strategy_params=None,
            start_dt=None,
            end_date=None,
            dispatch_mode=None,
            dispatch_rule=None,
            resource_pool={},
            strict_mode=True,
        )
    except ValidationError as exc:
        if exc.field != "priority_weight":
            raise RuntimeError(f"weighted strict_mode 首次失败字段异常：{exc.field!r}")
        if "读取失败" not in exc.message:
            raise RuntimeError(f"weighted strict_mode 未透出读取失败：{exc.message!r}")
    else:
        raise RuntimeError("weighted strict_mode=True 时 getter 读取失败应直接抛出 ValidationError")

    print("OK")


if __name__ == "__main__":
    main()

import os
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms.greedy.schedule_params import resolve_schedule_params
    from core.infrastructure.errors import ValidationError

    _assert_visible_read_failure(
        resolve_schedule_params,
        ValidationError,
        config=_ExplodingConfig(),
        strict_mode=False,
        expected_field="sort_strategy",
        expected_text="sort_strategy",
    )
    _assert_visible_read_failure(
        resolve_schedule_params,
        ValidationError,
        config=_ExplodingConfig(),
        strict_mode=True,
        expected_field="sort_strategy",
        expected_text="sort_strategy",
    )
    _assert_visible_read_failure(
        resolve_schedule_params,
        ValidationError,
        config=_ExplodingWeightedConfig(),
        strict_mode=False,
        expected_field="priority_weight",
        expected_text="priority_weight",
    )
    _assert_visible_read_failure(
        resolve_schedule_params,
        ValidationError,
        config=_ExplodingWeightedConfig(),
        strict_mode=True,
        expected_field="priority_weight",
        expected_text="priority_weight",
    )

    print("OK")


if __name__ == "__main__":
    main()

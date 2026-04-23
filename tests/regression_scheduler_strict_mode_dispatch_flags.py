import os
import sqlite3
import sys


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
    }



def _expect_validation(label, func, field):
    from core.infrastructure.errors import ValidationError

    try:
        func()
    except ValidationError as e:
        assert e.field == field, f"{label} 字段名异常：{e.field!r}"
        return
    raise AssertionError(f"{label} 应抛出 ValidationError(field={field!r})")



def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms.greedy.schedule_params import resolve_schedule_params
    from core.services.scheduler.config_service import ConfigService
    from core.services.scheduler.config_snapshot import ScheduleConfigSnapshot, build_schedule_config_snapshot
    from core.services.scheduler.config_validator import normalize_preset_snapshot

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

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    load_schema(conn, repo_root)

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

    print("OK")


if __name__ == "__main__":
    main()

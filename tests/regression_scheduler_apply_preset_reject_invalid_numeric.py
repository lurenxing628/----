"""守护 ConfigService.apply_preset 对非法预设的拒绝契约：非数字/NaN/Inf 数值字段、整数字段填小数、choice/yes-no 字段显式空白、以及缺省数值字段都必须抛 ValidationError 或返回 status=rejected，绝不静默回退默认基线；拒绝时不得写入 ACTIVE_PRESET / ACTIVE_PRESET_REASON 行。"""

import json
from typing import Optional


def _expect_validation_error(fn, title: str, field: Optional[str] = None) -> None:
    from core.infrastructure.errors import ValidationError

    ok = False
    try:
        fn()
    except ValidationError as exc:
        if field is not None and exc.field != field:
            raise AssertionError(f"{title}：字段异常，期望 {field!r}，实际 {exc.field!r}") from exc
        ok = True
    assert ok, f"{title}：应抛出 ValidationError"


def _save_preset_raw(cfg_svc, name: str, payload: dict) -> None:
    with cfg_svc.tx_manager.transaction():
        cfg_svc.repo.set(
            cfg_svc._preset_key(name),  # noqa: SLF001 - 回归脚本允许使用内部 key 约定
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            description="regression preset",
        )


def test_scheduler_apply_preset_reject_invalid_numeric(db_path) -> None:

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.scheduler import ConfigService

    conn = get_connection(db_path)

    try:
        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        base = cfg_svc.get_snapshot().to_dict()

        # 1) 非数字字符串（应拒绝）
        p1 = dict(base)
        p1["priority_weight"] = "abc"
        _save_preset_raw(cfg_svc, "bad_non_number", p1)
        _expect_validation_error(lambda: cfg_svc.apply_preset("bad_non_number"), "priority_weight=abc")

        # 2) 非有限数字 NaN/Inf（应拒绝）
        p2 = dict(base)
        p2["due_weight"] = "NaN"
        _save_preset_raw(cfg_svc, "bad_nan", p2)
        conn.execute(
            "DELETE FROM ScheduleConfig WHERE config_key IN (?, ?)",
            (cfg_svc.ACTIVE_PRESET_KEY, cfg_svc.ACTIVE_PRESET_REASON_KEY),
        )
        conn.commit()
        _expect_validation_error(lambda: cfg_svc.apply_preset("bad_nan"), "due_weight=NaN")
        remaining = conn.execute(
            "SELECT COUNT(1) FROM ScheduleConfig WHERE config_key IN (?, ?)",
            (cfg_svc.ACTIVE_PRESET_KEY, cfg_svc.ACTIVE_PRESET_REASON_KEY),
        ).fetchone()[0]
        assert int(remaining or 0) == 0

        p3 = dict(base)
        p3["holiday_default_efficiency"] = "Inf"
        _save_preset_raw(cfg_svc, "bad_inf", p3)
        _expect_validation_error(lambda: cfg_svc.apply_preset("bad_inf"), "holiday_default_efficiency=Inf")

        # 3) 整数字段非法（应拒绝）
        p4 = dict(base)
        p4["ortools_time_limit_seconds"] = "1.5"
        _save_preset_raw(cfg_svc, "bad_int_float", p4)
        _expect_validation_error(lambda: cfg_svc.apply_preset("bad_int_float"), "ortools_time_limit_seconds=1.5")

        # 4) 显式空白 choice / yes-no 字段（应拒绝）
        p5 = dict(base)
        p5["dispatch_mode"] = "   "
        _save_preset_raw(cfg_svc, "blank_dispatch_mode", p5)
        _expect_validation_error(lambda: cfg_svc.apply_preset("blank_dispatch_mode"), "dispatch_mode=blank", "dispatch_mode")

        p6 = dict(base)
        p6["auto_assign_enabled"] = "   "
        _save_preset_raw(cfg_svc, "blank_auto_assign_enabled", p6)
        _expect_validation_error(
            lambda: cfg_svc.apply_preset("blank_auto_assign_enabled"), "auto_assign_enabled=blank", "auto_assign_enabled"
        )

        p7 = dict(base)
        p7["sort_strategy"] = "   "
        _save_preset_raw(cfg_svc, "blank_sort_strategy", p7)
        _expect_validation_error(lambda: cfg_svc.apply_preset("blank_sort_strategy"), "sort_strategy=blank", "sort_strategy")

        p8 = dict(base)
        p8["algo_mode"] = "   "
        _save_preset_raw(cfg_svc, "blank_algo_mode", p8)
        _expect_validation_error(lambda: cfg_svc.apply_preset("blank_algo_mode"), "algo_mode=blank", "algo_mode")

        p9 = dict(base)
        p9["objective"] = "   "
        _save_preset_raw(cfg_svc, "blank_objective", p9)
        _expect_validation_error(lambda: cfg_svc.apply_preset("blank_objective"), "objective=blank", "objective")

        # 5) 缺省字段不再按默认基线静默回退（应拒绝）
        p10 = dict(base)
        p10.pop("priority_weight", None)
        p10.pop("due_weight", None)
        p10.pop("holiday_default_efficiency", None)
        _save_preset_raw(cfg_svc, "missing_numeric_allowed", p10)
        applied = cfg_svc.apply_preset("missing_numeric_allowed")
        remaining = conn.execute(
            "SELECT COUNT(1) FROM ScheduleConfig WHERE config_key IN (?, ?)",
            (cfg_svc.ACTIVE_PRESET_KEY, cfg_svc.ACTIVE_PRESET_REASON_KEY),
        ).fetchone()[0]
        assert applied["requested_preset"] == "missing_numeric_allowed"
        assert applied["effective_active_preset"] in {"", cfg_svc.ACTIVE_PRESET_CUSTOM}
        assert applied["status"] == "rejected"
        assert applied["adjusted_fields"] == []
        assert int(remaining or 0) == 0
        error_message = str(applied["error_message"] or "")
        assert "priority_weight" in error_message
        assert "due_weight" in error_message
        assert "holiday_default_efficiency" in error_message

    finally:
        try:
            conn.close()
        except Exception:
            pass



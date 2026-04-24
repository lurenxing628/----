from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.scheduler.config_service import ConfigService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def _default_page_payload() -> dict:
    defaults = default_snapshot_values()
    return {
        "sort_strategy": str(defaults["sort_strategy"]),
        "priority_weight": str(defaults["priority_weight"]),
        "due_weight": str(defaults["due_weight"]),
        "holiday_default_efficiency": str(defaults["holiday_default_efficiency"]),
        "prefer_primary_skill": str(defaults["prefer_primary_skill"]),
        "enforce_ready_default": str(defaults["enforce_ready_default"]),
        "dispatch_mode": str(defaults["dispatch_mode"]),
        "dispatch_rule": str(defaults["dispatch_rule"]),
        "auto_assign_enabled": str(defaults["auto_assign_enabled"]),
        "ortools_enabled": str(defaults["ortools_enabled"]),
        "ortools_time_limit_seconds": str(defaults["ortools_time_limit_seconds"]),
        "algo_mode": str(defaults["algo_mode"]),
        "objective": str(defaults["objective"]),
        "time_budget_seconds": str(defaults["time_budget_seconds"]),
        "freeze_window_enabled": str(defaults["freeze_window_enabled"]),
        "freeze_window_days": str(defaults["freeze_window_days"]),
    }


def test_get_snapshot_relaxed_mode_bootstraps_pristine_store_without_degradation() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        row_count_before = conn.execute("SELECT COUNT(1) FROM ScheduleConfig").fetchone()[0]
        assert int(row_count_before or 0) == 0

        snapshot = cfg_svc.get_snapshot(strict_mode=False)

        row_count_after = conn.execute("SELECT COUNT(1) FROM ScheduleConfig").fetchone()[0]
        assert int(row_count_after or 0) > 0
        assert tuple(snapshot.degradation_events or ()) == ()
        assert dict(snapshot.degradation_counters or {}) == {}
        assert snapshot.objective == cfg_svc.DEFAULT_OBJECTIVE
        assert cfg_svc.get_active_preset() == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert cfg_svc.get_active_preset_reason() is None
    finally:
        conn.close()


def test_get_snapshot_relaxed_mode_surfaces_missing_required_without_repairing_repo() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        conn.execute("DELETE FROM ScheduleConfig WHERE config_key = ?", ("objective",))
        conn.commit()

        missing_before = conn.execute(
            "SELECT COUNT(1) FROM ScheduleConfig WHERE config_key = ?",
            ("objective",),
        ).fetchone()[0]
        assert int(missing_before or 0) == 0

        snapshot = cfg_svc.get_snapshot(strict_mode=False)

        missing_after = conn.execute(
            "SELECT COUNT(1) FROM ScheduleConfig WHERE config_key = ?",
            ("objective",),
        ).fetchone()[0]
        assert int(missing_after or 0) == 0
        assert snapshot.objective == cfg_svc.DEFAULT_OBJECTIVE
        events = list(snapshot.degradation_events or ())
        assert any(
            isinstance(event, dict)
            and str(event.get("code") or "").strip() == "missing_required"
            and str(event.get("field") or "").strip() == "objective"
            for event in events
        ), events
    finally:
        conn.close()


def test_get_holiday_default_efficiency_strict_mode_bootstraps_pristine_store() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        row_count_before = conn.execute("SELECT COUNT(1) FROM ScheduleConfig").fetchone()[0]
        assert int(row_count_before or 0) == 0

        value = cfg_svc.get_holiday_default_efficiency(strict_mode=True)

        row_count_after = conn.execute("SELECT COUNT(1) FROM ScheduleConfig").fetchone()[0]
        assert value == cfg_svc.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY
        assert int(row_count_after or 0) > 0
    finally:
        conn.close()


def test_get_holiday_default_efficiency_strict_mode_reads_field_without_repairing_unrelated_missing() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        conn.execute("DELETE FROM ScheduleConfig WHERE config_key = ?", ("objective",))
        conn.execute(
            "UPDATE ScheduleConfig SET config_value = ? WHERE config_key = ?",
            ("0.75", "holiday_default_efficiency"),
        )
        conn.commit()

        value = cfg_svc.get_holiday_default_efficiency(strict_mode=True)
        objective_remaining = conn.execute(
            "SELECT COUNT(1) FROM ScheduleConfig WHERE config_key = ?",
            ("objective",),
        ).fetchone()[0]

        assert value == 0.75
        assert int(objective_remaining or 0) == 0
    finally:
        conn.close()


def test_get_holiday_default_efficiency_strict_mode_rejects_missing_field_in_dirty_store() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        conn.execute("DELETE FROM ScheduleConfig WHERE config_key = ?", ("holiday_default_efficiency",))
        conn.commit()

        with pytest.raises(ValidationError) as exc_info:
            cfg_svc.get_holiday_default_efficiency(strict_mode=True)

        remaining = conn.execute(
            "SELECT COUNT(1) FROM ScheduleConfig WHERE config_key = ?",
            ("holiday_default_efficiency",),
        ).fetchone()[0]

        assert exc_info.value.field == "holiday_default_efficiency"
        assert int(remaining or 0) == 0
    finally:
        conn.close()


def test_save_page_config_bootstraps_pristine_store_without_marking_custom() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        saved = cfg_svc.save_page_config(_default_page_payload())

        assert tuple(saved.effective_snapshot.degradation_events or ()) == ()
        assert dict(saved.effective_snapshot.degradation_counters or {}) == {}
        assert saved.effective_snapshot.objective == cfg_svc.DEFAULT_OBJECTIVE
        assert cfg_svc.get_active_preset() == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert cfg_svc.get_active_preset_reason() is None
    finally:
        conn.close()


def test_get_preset_display_state_readonly_keeps_missing_provenance_and_registered_field_unrepaired() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        conn.execute(
            "DELETE FROM ScheduleConfig WHERE config_key IN (?, ?, ?)",
            ("objective", cfg_svc.ACTIVE_PRESET_KEY, cfg_svc.ACTIVE_PRESET_REASON_KEY),
        )
        conn.commit()

        display_state = cfg_svc.get_preset_display_state(readonly=True)

        assert display_state["active_preset"] is None
        assert display_state["active_preset_reason"] is None
        assert display_state["active_preset_missing"] is True
        assert display_state["active_preset_reason_missing"] is True
        assert any(str(item.get("name") or "").strip() == cfg_svc.BUILTIN_PRESET_DEFAULT for item in display_state["presets"])
        remaining = {
            row["config_key"]
            for row in conn.execute(
                "SELECT config_key FROM ScheduleConfig WHERE config_key IN (?, ?, ?)",
                ("objective", cfg_svc.ACTIVE_PRESET_KEY, cfg_svc.ACTIVE_PRESET_REASON_KEY),
            ).fetchall()
        }
        assert remaining == set(), remaining
    finally:
        conn.close()


def test_get_preset_display_state_readonly_surfaces_missing_active_reason_without_repairing_repo() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        conn.execute("DELETE FROM ScheduleConfig WHERE config_key = ?", (cfg_svc.ACTIVE_PRESET_REASON_KEY,))
        conn.commit()

        first_state = cfg_svc.get_preset_display_state(readonly=True)
        second_state = cfg_svc.get_preset_display_state(readonly=True)

        remaining = conn.execute(
            "SELECT COUNT(1) FROM ScheduleConfig WHERE config_key = ?",
            (cfg_svc.ACTIVE_PRESET_REASON_KEY,),
        ).fetchone()[0]

        assert int(remaining or 0) == 0
        assert first_state["active_preset"] == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert first_state["active_preset_reason"] is None
        assert first_state["active_preset_missing"] is False
        assert first_state["active_preset_reason_missing"] is True
        assert first_state["current_config_state"]["state"] != "exact"
        assert first_state["current_config_state"]["provenance_missing"] is True
        assert first_state["current_config_state"]["baseline_key"] == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert first_state["current_config_state"]["baseline_label"] == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert first_state["current_config_state"]["baseline_source"] == "builtin"
        assert second_state["current_config_state"]["state"] != "exact"
        assert second_state["current_config_state"]["provenance_missing"] is True
        assert second_state["current_config_state"]["baseline_key"] == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert second_state["current_config_state"]["baseline_label"] == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert second_state["current_config_state"]["baseline_source"] == "builtin"
    finally:
        conn.close()


def test_get_preset_display_state_defaults_to_readonly_and_keeps_dirty_store_unchanged() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        conn.execute("DELETE FROM ScheduleConfig WHERE config_key = ?", ("objective",))
        conn.commit()

        before = conn.execute("SELECT COUNT(1) FROM ScheduleConfig").fetchone()[0]
        display_state = cfg_svc.get_preset_display_state()
        after = conn.execute("SELECT COUNT(1) FROM ScheduleConfig").fetchone()[0]
        objective_remaining = conn.execute(
            "SELECT COUNT(1) FROM ScheduleConfig WHERE config_key = ?",
            ("objective",),
        ).fetchone()[0]

        assert display_state["readonly"] is True
        assert int(before or 0) == int(after or 0)
        assert int(objective_remaining or 0) == 0
    finally:
        conn.close()


def test_direct_getters_do_not_repair_missing_provenance_or_registered_fields() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        conn.execute(
            "DELETE FROM ScheduleConfig WHERE config_key IN (?, ?, ?)",
            ("objective", cfg_svc.ACTIVE_PRESET_KEY, cfg_svc.ACTIVE_PRESET_REASON_KEY),
        )
        conn.commit()

        assert cfg_svc.get("objective") is None
        assert cfg_svc.get_active_preset() is None
        assert cfg_svc.get_active_preset_reason() is None

        remaining = {
            row["config_key"]
            for row in conn.execute(
                "SELECT config_key FROM ScheduleConfig WHERE config_key IN (?, ?, ?)",
                ("objective", cfg_svc.ACTIVE_PRESET_KEY, cfg_svc.ACTIVE_PRESET_REASON_KEY),
            ).fetchall()
        }
        assert remaining == set(), remaining
    finally:
        conn.close()

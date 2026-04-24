from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.config_service import ConfigService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def test_config_page_save_outcome_keeps_legacy_positional_constructor_order() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        snapshot = cfg_svc.get_snapshot()

        outcome_cls = type(cfg_svc.save_page_config(snapshot.to_dict()))
        outcome = outcome_cls(snapshot, ["sort_strategy"])

        assert outcome.visible_changed_fields == ["sort_strategy"]
        assert outcome.status == "saved"
        assert outcome.normalized_snapshot is None
    finally:
        conn.close()


def test_config_service_manual_set_marks_active_preset_custom() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        assert cfg_svc.get_active_preset() == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert cfg_svc.get_active_preset_reason() is None

        saved = cfg_svc.save_preset("我的方案")
        assert saved["status"] == "saved"
        assert saved["requested_preset"] == "我的方案"
        assert saved["effective_active_preset"] == "我的方案"
        assert cfg_svc.get_active_preset() == "我的方案"
        assert cfg_svc.get_active_preset_reason() is None

        cfg_svc.set_dispatch("sgs", "slack")
        assert cfg_svc.get_active_preset() == cfg_svc.ACTIVE_PRESET_CUSTOM
        reason = cfg_svc.get_active_preset_reason() or ""
        assert "手工" in reason, f"手工修改后 active_preset_reason 异常：{reason!r}"
    finally:
        conn.close()


def test_config_service_apply_saved_preset_keeps_active_name() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        saved = cfg_svc.save_preset("current-demo")
        assert saved["status"] == "saved"
        assert saved["effective_active_preset"] == "current-demo"
        assert cfg_svc.get_active_preset() == "current-demo"

        applied = cfg_svc.apply_preset("current-demo")
        assert applied["status"] == "applied"
        assert applied["requested_preset"] == "current-demo"
        assert applied["effective_active_preset"] == "current-demo"
        assert applied["adjusted_fields"] == []
        assert cfg_svc.get_active_preset() == "current-demo"
        assert cfg_svc.get_active_preset_reason() is None
    finally:
        conn.close()


def test_config_service_apply_legacy_preset_missing_hidden_field_is_rejected() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        payload = cfg_svc.get_snapshot().to_dict()
        payload.pop("auto_assign_persist", None)

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                cfg_svc._preset_key("legacy-demo"),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                description="legacy preset",
            )

        before = cfg_svc.get_snapshot(strict_mode=True).to_dict()

        applied = cfg_svc.apply_preset("legacy-demo")
        assert applied["status"] == "rejected"
        assert applied["requested_preset"] == "legacy-demo"
        assert applied["effective_active_preset"] == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert applied["adjusted_fields"] == []
        assert applied["error_fields"] == ["auto_assign_persist"]
        assert cfg_svc.get_active_preset() == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert cfg_svc.get_active_preset_reason() is None
        assert "auto_assign_persist" in str(applied["error_message"] or "")
        assert cfg_svc.get_snapshot(strict_mode=True).to_dict() == before
    finally:
        conn.close()


def test_config_service_apply_legacy_shape_preset_keeps_active_name() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        payload = cfg_svc.get_snapshot().to_dict()
        payload.update(
            {
                "sort_strategy": " WEIGHTED ",
                "priority_weight": "40",
                "due_weight": "50",
                "dispatch_mode": " SGS ",
                "dispatch_rule": " SLACK ",
                "objective": " MIN_CHANGEOVER ",
            }
        )
        payload["auto_assign_persist"] = " YES "

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                cfg_svc._preset_key("legacy-shape"),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                description="legacy shape preset",
            )

        applied = cfg_svc.apply_preset("legacy-shape")
        assert applied["status"] == "adjusted"
        assert applied["requested_preset"] == "legacy-shape"
        assert applied["effective_active_preset"] == "legacy-shape"
        assert any(field in list(applied["adjusted_fields"] or []) for field in ("sort_strategy", "priority_weight", "dispatch_mode"))
        assert cfg_svc.get_active_preset() == "legacy-shape"
        reason = cfg_svc.get_active_preset_reason() or ""
        assert cfg_svc.ACTIVE_PRESET_REASON_PRESET_ADJUSTED in reason
        assert any(field in reason for field in ("sort_strategy", "priority_weight", "dispatch_mode")), reason
        snap = cfg_svc.get_snapshot(strict_mode=True)
        assert snap.sort_strategy == "weighted"
        assert snap.priority_weight == 0.4
        assert snap.due_weight == 0.5
        assert snap.objective == "min_changeover"
    finally:
        conn.close()


def test_config_service_apply_preset_with_unknown_top_level_key_keeps_active_name() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        payload = cfg_svc.get_snapshot().to_dict()
        payload["legacy_runtime_block"] = {"foo": "bar"}

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                cfg_svc._preset_key("legacy-extra-key"),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                description="legacy extra key preset",
            )

        applied = cfg_svc.apply_preset("legacy-extra-key")
        assert applied["status"] == "adjusted"
        assert applied["requested_preset"] == "legacy-extra-key"
        assert applied["effective_active_preset"] == "legacy-extra-key"
        assert "legacy_runtime_block" in list(applied["adjusted_fields"] or [])
        assert cfg_svc.get_active_preset() == "legacy-extra-key"
        reason = cfg_svc.get_active_preset_reason() or ""
        assert cfg_svc.ACTIVE_PRESET_REASON_PRESET_ADJUSTED in reason
        assert "legacy_runtime_block" in reason
    finally:
        conn.close()


def test_config_service_page_save_is_atomic_when_validation_fails() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        cfg_svc.save_preset("atomic-demo")
        before = cfg_svc.get_snapshot(strict_mode=True)

        try:
            cfg_svc.save_page_config(
                {
                    "sort_strategy": "weighted",
                    "priority_weight": "0.4",
                    "due_weight": "0.5",
                    "holiday_default_efficiency": "0.8",
                    "prefer_primary_skill": "yes",
                    "enforce_ready_default": "yes",
                    "dispatch_mode": "sgs",
                    "dispatch_rule": "cr",
                    "auto_assign_enabled": "yes",
                    "ortools_enabled": "no",
                    "ortools_time_limit_seconds": "5",
                    "algo_mode": "improve",
                    "objective": "not-a-valid-objective",
                    "time_budget_seconds": "30",
                    "freeze_window_enabled": "yes",
                    "freeze_window_days": "2",
                }
            )
        except ValidationError as exc:
            assert exc.field == "objective"
        else:
            raise AssertionError("非法 objective 应阻止整次配置保存")

        after = cfg_svc.get_snapshot(strict_mode=True)
        assert after.to_dict() == before.to_dict()
        assert cfg_svc.get_active_preset() == "atomic-demo"
        assert cfg_svc.get_active_preset_reason() is None
    finally:
        conn.close()


def test_config_service_page_save_rejects_mixed_unit_weights_without_writing() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        before = cfg_svc.get_snapshot(strict_mode=True)

        try:
            cfg_svc.save_page_config(
                {
                    "sort_strategy": "weighted",
                    "priority_weight": "40",
                    "due_weight": "0.5",
                    "holiday_default_efficiency": "0.8",
                    "prefer_primary_skill": "no",
                    "enforce_ready_default": "no",
                    "dispatch_mode": "batch_order",
                    "dispatch_rule": "slack",
                    "auto_assign_enabled": "no",
                    "ortools_enabled": "no",
                    "ortools_time_limit_seconds": "5",
                    "algo_mode": "greedy",
                    "objective": "min_overdue",
                    "time_budget_seconds": "20",
                    "freeze_window_enabled": "no",
                    "freeze_window_days": "3",
                }
            )
        except ValidationError as exc:
            assert exc.field == "权重"
        else:
            raise AssertionError("mixed-unit 权重输入应被拒绝")

        after = cfg_svc.get_snapshot(strict_mode=True)
        assert after.priority_weight == before.priority_weight
        assert after.due_weight == before.due_weight
        assert after.ready_weight == before.ready_weight
        assert cfg_svc.get_active_preset() == cfg_svc.BUILTIN_PRESET_DEFAULT
    finally:
        conn.close()


def test_config_service_page_save_rejects_blank_time_budget() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        before = cfg_svc.get_snapshot(strict_mode=True)

        with pytest.raises(ValidationError) as exc_info:
            cfg_svc.save_page_config(
                {
                    "sort_strategy": "due_date_first",
                    "priority_weight": "0.4",
                    "due_weight": "0.5",
                    "holiday_default_efficiency": "0.9",
                    "prefer_primary_skill": "yes",
                    "enforce_ready_default": "yes",
                    "dispatch_mode": "sgs",
                    "dispatch_rule": "cr",
                    "auto_assign_enabled": "yes",
                    "ortools_enabled": "no",
                    "ortools_time_limit_seconds": "5",
                    "algo_mode": "improve",
                    "objective": "min_tardiness",
                    "time_budget_seconds": "",
                    "freeze_window_enabled": "yes",
                    "freeze_window_days": "4",
                }
            )

        assert exc_info.value.field in {"time_budget_seconds", "计算时间上限"}
        assert cfg_svc.get_snapshot(strict_mode=True).time_budget_seconds == before.time_budget_seconds
        assert cfg_svc.get_snapshot(strict_mode=True).sort_strategy == before.sort_strategy
    finally:
        conn.close()


def test_config_service_page_save_repairs_allowlisted_hidden_fields() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                "auto_assign_persist",
                "MAYBE",
                description=cfg_svc._field_description("auto_assign_persist"),
            )

        cfg_svc.save_page_config(
            {
                "sort_strategy": "priority_first",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "holiday_default_efficiency": "0.9",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "yes",
                "dispatch_mode": "sgs",
                "dispatch_rule": "cr",
                "auto_assign_enabled": "yes",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "improve",
                "objective": "min_tardiness",
                "time_budget_seconds": "18",
                "freeze_window_enabled": "yes",
                "freeze_window_days": "2",
            }
        )

        assert cfg_svc.repo.get_value("auto_assign_persist", default=None) == "yes"
        assert cfg_svc.get("auto_assign_persist") == "yes"
    finally:
        conn.close()


def test_config_service_page_save_hidden_repair_keeps_named_preset_provenance() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        saved = cfg_svc.save_preset("legacy-demo")
        assert saved["effective_active_preset"] == "legacy-demo"

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                "auto_assign_persist",
                "MAYBE",
                description=cfg_svc._field_description("auto_assign_persist"),
            )

        outcome = cfg_svc.save_page_config(
            {
                "sort_strategy": "priority_first",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "holiday_default_efficiency": "0.8",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "no",
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "greedy",
                "objective": "min_overdue",
                "time_budget_seconds": "20",
                "freeze_window_enabled": "no",
                "freeze_window_days": "0",
            }
        )

        assert outcome.hidden_repaired_fields == ["auto_assign_persist"]
        assert outcome.blocked_hidden_repairs == []
        assert cfg_svc.get("auto_assign_persist") == "yes"
        assert cfg_svc.get_active_preset() == "legacy-demo"
        reason = cfg_svc.get_active_preset_reason() or ""
        assert cfg_svc.ACTIVE_PRESET_REASON_HIDDEN_REPAIR in reason
        assert "auto_assign_persist" in reason
        display_state = cfg_svc.get_preset_display_state(readonly=True)
        current_config_state = dict(display_state.get("current_config_state") or {})
        assert current_config_state["state"] == "exact"
        assert current_config_state["baseline_source"] == "named"
        assert current_config_state["is_custom"] is False
        assert current_config_state["repair_notice"]["kind"] == "hidden"
        assert "自动分配结果回写" in list(current_config_state["repair_notice"]["field_labels"] or [])
        assert "auto_assign_persist" not in str(current_config_state)
        assert "自动分配结果回写" in str(current_config_state)
        public_outcome = outcome.to_public_outcome_dict()
        assert "auto_assign_persist" not in str(public_outcome)
        assert "自动分配结果回写" in str(public_outcome)
    finally:
        conn.close()


def test_get_preset_display_state_named_baseline_drift_is_not_exact() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        saved = cfg_svc.save_preset("drift-demo")
        assert saved["effective_active_preset"] == "drift-demo"

        drifted_payload = cfg_svc.get_snapshot(strict_mode=True).to_dict()
        drifted_payload["sort_strategy"] = "due_date_first"
        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                cfg_svc._preset_key("drift-demo"),
                json.dumps(drifted_payload, ensure_ascii=False, sort_keys=True),
                description="drifted preset payload",
            )

        display_state = cfg_svc.get_preset_display_state(readonly=True)

        assert display_state["active_preset"] == "drift-demo"
        assert display_state["provenance_missing"] is False
        assert display_state["can_preserve_baseline"] is False
        current_config_state = dict(display_state.get("current_config_state") or {})
        assert current_config_state["state"] == "adjusted"
        assert current_config_state["baseline_source"] == "named"
        assert current_config_state["provenance_missing"] is False
        assert "drift-demo" in str(current_config_state.get("label") or "")
    finally:
        conn.close()


def test_get_preset_display_state_missing_named_baseline_is_not_exact() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        saved = cfg_svc.save_preset("missing-demo")
        assert saved["effective_active_preset"] == "missing-demo"

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.delete(cfg_svc._preset_key("missing-demo"))

        display_state = cfg_svc.get_preset_display_state(readonly=True)

        assert display_state["active_preset"] == "missing-demo"
        assert display_state["provenance_missing"] is False
        assert display_state["can_preserve_baseline"] is False
        current_config_state = dict(display_state.get("current_config_state") or {})
        assert current_config_state["state"] == "adjusted"
        assert current_config_state["status_label"] == "基线不可验证"
        assert current_config_state["baseline_source"] == "named"
        assert current_config_state["baseline_probe_failed"] is True
        assert "missing-demo" in str(current_config_state.get("label") or "")
    finally:
        conn.close()


def test_get_preset_display_state_builtin_baseline_drift_stays_exact_after_reapply() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        drifted_payload = cfg_svc.get_snapshot(strict_mode=True).to_dict()
        drifted_payload["sort_strategy"] = "due_date_first"
        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                cfg_svc._preset_key(cfg_svc.BUILTIN_PRESET_DEFAULT),
                json.dumps(drifted_payload, ensure_ascii=False, sort_keys=True),
                description="drifted builtin preset payload",
            )

        applied = cfg_svc.apply_preset(cfg_svc.BUILTIN_PRESET_DEFAULT)
        display_state = cfg_svc.get_preset_display_state(readonly=True)

        assert applied["status"] == "applied"
        assert display_state["active_preset"] == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert display_state["provenance_missing"] is False
        assert display_state["can_preserve_baseline"] is True
        current_config_state = dict(display_state.get("current_config_state") or {})
        assert current_config_state["state"] == "exact"
        assert current_config_state["baseline_source"] == "builtin"
        assert current_config_state["baseline_probe_failed"] is False
    finally:
        conn.close()


def test_get_preset_display_state_builtin_baseline_without_repo_row_stays_exact_and_apply_matches() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.delete(cfg_svc._preset_key(cfg_svc.BUILTIN_PRESET_DEFAULT))

        applied = cfg_svc.apply_preset(cfg_svc.BUILTIN_PRESET_DEFAULT)
        display_state = cfg_svc.get_preset_display_state(readonly=True)
        current_config_state = dict(display_state.get("current_config_state") or {})

        assert applied["status"] == "applied"
        assert applied["requested_preset"] == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert applied["effective_active_preset"] == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert display_state["active_preset"] == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert display_state["can_preserve_baseline"] is True
        assert current_config_state["state"] == "exact"
        assert current_config_state["baseline_source"] == "builtin"
        assert current_config_state["baseline_probe_failed"] is False
    finally:
        conn.close()


def test_get_preset_display_state_named_baseline_missing_registered_field_is_not_exact() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        saved = cfg_svc.save_preset("legacy-missing-field")
        assert saved["effective_active_preset"] == "legacy-missing-field"

        payload = json.loads(cfg_svc.repo.get_value(cfg_svc._preset_key("legacy-missing-field"), default="{}"))
        payload.pop("auto_assign_persist", None)
        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                cfg_svc._preset_key("legacy-missing-field"),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                description="legacy missing field preset",
            )

        display_state = cfg_svc.get_preset_display_state(readonly=True)
        current_config_state = dict(display_state.get("current_config_state") or {})

        assert display_state["active_preset"] == "legacy-missing-field"
        assert display_state["can_preserve_baseline"] is False
        assert current_config_state["state"] == "adjusted"
        assert current_config_state["status_label"] == "基线不可验证"
        assert current_config_state["baseline_source"] == "named"
        assert current_config_state["baseline_probe_failed"] is True
    finally:
        conn.close()


def test_config_service_page_save_hidden_repair_blocks_adjusted_named_provenance() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        payload = cfg_svc.get_snapshot().to_dict()
        payload.update(
            {
                "sort_strategy": " WEIGHTED ",
                "priority_weight": "40",
                "due_weight": "50",
                "dispatch_mode": " SGS ",
                "dispatch_rule": " SLACK ",
                "objective": " MIN_CHANGEOVER ",
                "auto_assign_persist": " YES ",
            }
        )

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                cfg_svc._preset_key("legacy-shape"),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                description="legacy shape preset",
            )

        applied = cfg_svc.apply_preset("legacy-shape")
        assert applied["status"] == "adjusted"
        assert cfg_svc.ACTIVE_PRESET_REASON_PRESET_ADJUSTED in str(cfg_svc.get_active_preset_reason() or "")

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                "auto_assign_persist",
                "MAYBE",
                description=cfg_svc._field_description("auto_assign_persist"),
            )

        saved = cfg_svc.save_page_config(
            {
                "sort_strategy": "weighted",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "holiday_default_efficiency": "0.8",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "no",
                "dispatch_mode": "sgs",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "greedy",
                "objective": "min_changeover",
                "time_budget_seconds": "20",
                "freeze_window_enabled": "no",
                "freeze_window_days": "0",
            }
        )

        display_state = cfg_svc.get_preset_display_state(readonly=True)
        current_config_state = dict(display_state.get("current_config_state") or {})
        reason = str(cfg_svc.get_active_preset_reason() or "")

        assert saved.hidden_repaired_fields == []
        assert saved.blocked_hidden_repairs == ["auto_assign_persist"]
        assert saved.status == "blocked_hidden_repair"
        assert saved.normalized_snapshot.auto_assign_persist == "yes"
        assert saved.auto_assign_persist == "yes"
        assert saved.to_dict()["auto_assign_persist"] == "yes"
        assert saved.to_snapshot_dict()["auto_assign_persist"] == "yes"
        outcome = saved.to_outcome_dict()
        assert outcome["effective_snapshot"]["auto_assign_persist"] == "yes"
        assert "snapshot" not in outcome
        assert outcome["raw_persisted_values"]["auto_assign_persist"] == "MAYBE"
        assert outcome["raw_effective_mismatches"] == [
            {"field": "auto_assign_persist", "effective_value": "yes", "raw_value": "MAYBE"}
        ]
        assert outcome["raw_missing_fields"] == []
        public_outcome = saved.to_public_outcome_dict()
        assert public_outcome["status"] == "blocked_hidden_repair"
        assert "auto_assign_persist" not in public_outcome["effective_snapshot"]
        assert "raw_persisted_values" not in public_outcome
        assert "raw_effective_mismatches" not in public_outcome
        assert "MAYBE" not in str(public_outcome)
        assert "auto_assign_persist" not in str(public_outcome)
        assert "自动分配结果回写" in str(public_outcome)
        assert any(event.get("field") == "auto_assign_persist" for event in saved.effective_snapshot.degradation_events)
        assert cfg_svc.get("auto_assign_persist") == "MAYBE"
        assert cfg_svc.get_active_preset() == "legacy-shape"
        assert cfg_svc.ACTIVE_PRESET_REASON_PRESET_ADJUSTED in reason
        assert cfg_svc.ACTIVE_PRESET_REASON_HIDDEN_REPAIR not in reason
        assert current_config_state["state"] == "adjusted"
        assert current_config_state["baseline_source"] == "named"
        assert current_config_state["repair_notice"]["kind"] == "none"
    finally:
        conn.close()


def test_config_service_page_save_hidden_repair_preserves_custom_reason() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(cfg_svc.ACTIVE_PRESET_KEY, cfg_svc.ACTIVE_PRESET_CUSTOM, description="active preset")
            cfg_svc.repo.set(
                cfg_svc.ACTIVE_PRESET_REASON_KEY,
                cfg_svc.ACTIVE_PRESET_REASON_MANUAL,
                description="active reason",
            )
            cfg_svc.repo.set(
                "auto_assign_persist",
                "MAYBE",
                description=cfg_svc._field_description("auto_assign_persist"),
            )

        saved = cfg_svc.save_page_config(
            {
                "sort_strategy": "weighted",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "holiday_default_efficiency": "0.8",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "no",
                "dispatch_mode": "sgs",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "greedy",
                "objective": "min_changeover",
                "time_budget_seconds": "20",
                "freeze_window_enabled": "no",
                "freeze_window_days": "0",
            }
        )
        display_state = cfg_svc.get_preset_display_state(readonly=True)
        current_config_state = dict(display_state.get("current_config_state") or {})
        repair_notices = list(current_config_state.get("repair_notices") or [])

        assert saved.status == "repaired_hidden"
        assert saved.hidden_repaired_fields == ["auto_assign_persist"]
        assert saved.blocked_hidden_repairs == []
        assert cfg_svc.get_active_preset() == cfg_svc.ACTIVE_PRESET_CUSTOM
        assert cfg_svc.get_active_preset_reason() == cfg_svc.ACTIVE_PRESET_REASON_MANUAL
        assert any(notice.get("kind") == "hidden" for notice in repair_notices)
    finally:
        conn.close()


def test_config_service_page_save_hidden_repair_with_custom_empty_reason_stays_blocked() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(cfg_svc.ACTIVE_PRESET_KEY, cfg_svc.ACTIVE_PRESET_CUSTOM, description="active preset")
            cfg_svc.repo.set(cfg_svc.ACTIVE_PRESET_REASON_KEY, "", description="active reason")
            cfg_svc.repo.set(
                "auto_assign_persist",
                "MAYBE",
                description=cfg_svc._field_description("auto_assign_persist"),
            )

        saved = cfg_svc.save_page_config(
            {
                "sort_strategy": "priority_first",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "holiday_default_efficiency": "0.8",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "no",
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "greedy",
                "objective": "min_overdue",
                "time_budget_seconds": "20",
                "freeze_window_enabled": "no",
                "freeze_window_days": "0",
            }
        )
        display_state = cfg_svc.get_preset_display_state(readonly=True)
        current_config_state = dict(display_state.get("current_config_state") or {})

        assert saved.status == "blocked_hidden_repair"
        assert saved.hidden_repaired_fields == []
        assert saved.blocked_hidden_repairs == ["auto_assign_persist"]
        assert cfg_svc.get("auto_assign_persist") == "MAYBE"
        assert cfg_svc.get_active_preset() == cfg_svc.ACTIVE_PRESET_CUSTOM
        assert cfg_svc.get_active_preset_reason() is None
        assert display_state["active_preset_reason_missing"] is False
        assert current_config_state["provenance_missing"] is True
        assert current_config_state["baseline_source"] == "unknown"
    finally:
        conn.close()


def test_config_service_visible_change_does_not_smuggle_hidden_repair_without_provenance() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(cfg_svc.ACTIVE_PRESET_KEY, cfg_svc.ACTIVE_PRESET_CUSTOM, description="active preset")
            cfg_svc.repo.set(cfg_svc.ACTIVE_PRESET_REASON_KEY, "", description="active reason")
            cfg_svc.repo.set(
                "auto_assign_persist",
                "MAYBE",
                description=cfg_svc._field_description("auto_assign_persist"),
            )

        saved = cfg_svc.save_page_config(
            {
                "sort_strategy": "weighted",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "holiday_default_efficiency": "0.8",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "no",
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "greedy",
                "objective": "min_overdue",
                "time_budget_seconds": "20",
                "freeze_window_enabled": "no",
                "freeze_window_days": "0",
            }
        )

        assert saved.status == "blocked_hidden_repair"
        assert saved.hidden_repaired_fields == []
        assert saved.blocked_hidden_repairs == ["auto_assign_persist"]
        assert cfg_svc.get("sort_strategy") == "weighted"
        assert cfg_svc.get("auto_assign_persist") == "MAYBE"
        assert cfg_svc.get_active_preset() == cfg_svc.ACTIVE_PRESET_CUSTOM
        assert cfg_svc.get_active_preset_reason() == cfg_svc.ACTIVE_PRESET_REASON_MANUAL
    finally:
        conn.close()


def test_config_service_page_save_reports_bad_active_preset_meta_without_marking_runtime_degraded() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(cfg_svc.ACTIVE_PRESET_KEY, "custom", description="active preset")
            cfg_svc.repo.set(cfg_svc.ACTIVE_PRESET_REASON_KEY, "manual", description="active reason")
            cfg_svc.repo.set(cfg_svc.ACTIVE_PRESET_META_KEY, "{bad json", description="bad meta")

        saved = cfg_svc.save_page_config(cfg_svc.get_snapshot().to_dict())
        outcome = saved.to_outcome_dict()

        assert saved.status in {"saved", "unchanged"}
        assert outcome["meta_parse_warnings"] == [
            {
                "field": cfg_svc.ACTIVE_PRESET_META_KEY,
                "message": "active_preset_meta 不是有效 JSON，已按历史来源信息继续显示。",
            }
        ]
        assert outcome["degradation_events"] == []
    finally:
        conn.close()


def test_config_service_page_save_visible_repair_marks_custom_with_visible_repair_reason() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        saved = cfg_svc.save_preset("legacy-demo")
        assert saved["effective_active_preset"] == "legacy-demo"

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                "holiday_default_efficiency",
                "NaN",
                description=cfg_svc._field_description("holiday_default_efficiency"),
            )

        repaired = cfg_svc.save_page_config(
            {
                "sort_strategy": "priority_first",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "holiday_default_efficiency": "0.8",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "no",
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "greedy",
                "objective": "min_overdue",
                "time_budget_seconds": "20",
                "freeze_window_enabled": "no",
                "freeze_window_days": "0",
            }
        )

        assert repaired.effective_snapshot.holiday_default_efficiency == 0.8
        assert repaired.visible_repaired_fields == ["holiday_default_efficiency"]
        assert repaired.hidden_repaired_fields == []
        assert cfg_svc.get("holiday_default_efficiency") == "0.8"
        assert cfg_svc.get_active_preset() == cfg_svc.ACTIVE_PRESET_CUSTOM
        assert cfg_svc.get_active_preset_reason() == cfg_svc.ACTIVE_PRESET_REASON_VISIBLE_REPAIR
    finally:
        conn.close()


def test_config_service_page_save_ready_weight_repair_marks_custom_with_visible_repair_reason() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        saved = cfg_svc.save_preset("legacy-demo")
        assert saved["effective_active_preset"] == "legacy-demo"

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                "ready_weight",
                "NaN",
                description=cfg_svc._field_description("ready_weight"),
            )

        repaired = cfg_svc.save_page_config(
            {
                "sort_strategy": "priority_first",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "holiday_default_efficiency": "0.8",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "no",
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "greedy",
                "objective": "min_overdue",
                "time_budget_seconds": "20",
                "freeze_window_enabled": "no",
                "freeze_window_days": "0",
            }
        )

        assert repaired.visible_repaired_fields == ["ready_weight"]
        assert repaired.hidden_repaired_fields == []
        assert abs(float(cfg_svc.get("ready_weight") or 0.0) - 0.1) < 1e-9
        assert cfg_svc.get_active_preset() == cfg_svc.ACTIVE_PRESET_CUSTOM
        assert cfg_svc.get_active_preset_reason() == cfg_svc.ACTIVE_PRESET_REASON_VISIBLE_REPAIR
    finally:
        conn.close()


def test_config_service_page_save_omitted_visible_degraded_field_does_not_persist_fallback() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        saved = cfg_svc.save_preset("legacy-demo")
        assert saved["effective_active_preset"] == "legacy-demo"

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                "holiday_default_efficiency",
                "NaN",
                description=cfg_svc._field_description("holiday_default_efficiency"),
            )

        repaired = cfg_svc.save_page_config(
            {
                "sort_strategy": "priority_first",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "no",
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "greedy",
                "objective": "min_overdue",
                "time_budget_seconds": "20",
                "freeze_window_enabled": "no",
                "freeze_window_days": "0",
            }
        )

        display_state = cfg_svc.get_preset_display_state(readonly=True)
        current_config_state = dict(display_state.get("current_config_state") or {})

        assert repaired.effective_snapshot.holiday_default_efficiency == 0.8
        assert cfg_svc.get("holiday_default_efficiency") == "NaN"
        assert cfg_svc.get_active_preset() == "legacy-demo"
        assert cfg_svc.get_active_preset_reason() != cfg_svc.ACTIVE_PRESET_REASON_VISIBLE_REPAIR
        assert current_config_state["degraded"] is True
    finally:
        conn.close()


def test_config_service_page_save_visible_and_hidden_repairs_preserve_structured_meta() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                "holiday_default_efficiency",
                "NaN",
                description=cfg_svc._field_description("holiday_default_efficiency"),
            )
            cfg_svc.repo.set(
                "auto_assign_persist",
                "MAYBE",
                description=cfg_svc._field_description("auto_assign_persist"),
            )

        cfg_svc.save_page_config(
            {
                "sort_strategy": "priority_first",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "holiday_default_efficiency": "0.8",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "no",
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "greedy",
                "objective": "min_overdue",
                "time_budget_seconds": "20",
                "freeze_window_enabled": "no",
                "freeze_window_days": "0",
            }
        )

        meta = cfg_svc.get_active_preset_meta()
        notices = list(meta.get("repair_notices") or [])
        kinds = [str(item.get("kind") or "") for item in notices]
        display_state = cfg_svc.get_preset_display_state(readonly=True)
        current_config_state = dict(display_state.get("current_config_state") or {})

        assert cfg_svc.get_active_preset() == cfg_svc.ACTIVE_PRESET_CUSTOM
        assert cfg_svc.get_active_preset_reason() == cfg_svc.ACTIVE_PRESET_REASON_VISIBLE_REPAIR
        assert meta.get("reason_code") == cfg_svc.ACTIVE_PRESET_META_REASON_VISIBLE_REPAIR
        assert kinds[:2] == ["visible", "hidden"], notices
        assert "auto_assign_persist" in list((notices[1] or {}).get("fields") or [])
        assert [str(item.get("kind") or "") for item in (current_config_state.get("repair_notices") or [])][:2] == [
            "visible",
            "hidden",
        ]
        assert current_config_state["repair_notice"]["kind"] == "visible"
    finally:
        conn.close()


def test_config_service_page_save_noop_keeps_existing_preset_provenance() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        saved = cfg_svc.save_preset("current-demo")
        assert saved["effective_active_preset"] == "current-demo"

        cfg_svc.save_page_config(
            {
                "sort_strategy": "priority_first",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "holiday_default_efficiency": "0.8",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "no",
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "greedy",
                "objective": "min_overdue",
                "time_budget_seconds": "20",
                "freeze_window_enabled": "no",
                "freeze_window_days": "0",
            }
        )

        assert cfg_svc.get_active_preset() == "current-demo"
        assert cfg_svc.get_active_preset_reason() is None
    finally:
        conn.close()


def test_config_service_page_save_noop_does_not_write_repo_updates() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        saved = cfg_svc.save_preset("current-demo")
        assert saved["effective_active_preset"] == "current-demo"

        set_batch_calls = []
        original_set_batch = cfg_svc.repo.set_batch

        def recording_set_batch(entries):
            payload = list(entries)
            set_batch_calls.append(payload)
            return original_set_batch(payload)

        cfg_svc.repo.set_batch = recording_set_batch
        try:
            cfg_svc.save_page_config(
                {
                    "sort_strategy": "priority_first",
                    "priority_weight": "0.4",
                    "due_weight": "0.5",
                    "holiday_default_efficiency": "0.8",
                    "prefer_primary_skill": "no",
                    "enforce_ready_default": "no",
                    "dispatch_mode": "batch_order",
                    "dispatch_rule": "slack",
                    "auto_assign_enabled": "no",
                    "ortools_enabled": "no",
                    "ortools_time_limit_seconds": "5",
                    "algo_mode": "greedy",
                    "objective": "min_overdue",
                    "time_budget_seconds": "20",
                    "freeze_window_enabled": "no",
                    "freeze_window_days": "0",
                }
            )
        finally:
            cfg_svc.repo.set_batch = original_set_batch

        assert set_batch_calls == []
    finally:
        conn.close()


def test_config_service_page_save_hidden_repair_without_provenance_stays_blocked() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        conn.execute(
            "DELETE FROM ScheduleConfig WHERE config_key IN (?, ?)",
            (cfg_svc.ACTIVE_PRESET_KEY, cfg_svc.ACTIVE_PRESET_REASON_KEY),
        )
        conn.commit()

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                "auto_assign_persist",
                "MAYBE",
                description=cfg_svc._field_description("auto_assign_persist"),
            )

        saved = cfg_svc.save_page_config(
            {
                "sort_strategy": "priority_first",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "holiday_default_efficiency": "0.8",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "no",
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "greedy",
                "objective": "min_overdue",
                "time_budget_seconds": "20",
                "freeze_window_enabled": "no",
                "freeze_window_days": "0",
            }
        )

        remaining = {
            row["config_key"]
            for row in conn.execute(
                "SELECT config_key FROM ScheduleConfig WHERE config_key IN (?, ?)",
                (cfg_svc.ACTIVE_PRESET_KEY, cfg_svc.ACTIVE_PRESET_REASON_KEY),
            ).fetchall()
        }
        assert cfg_svc.ACTIVE_PRESET_KEY not in remaining
        assert cfg_svc.ACTIVE_PRESET_REASON_KEY not in remaining
        assert saved.hidden_repaired_fields == []
        assert saved.blocked_hidden_repairs == ["auto_assign_persist"]
        assert saved.status == "blocked_hidden_repair"
        assert saved.normalized_snapshot.auto_assign_persist == "yes"
        assert any(event.get("field") == "auto_assign_persist" for event in saved.effective_snapshot.degradation_events)
        assert cfg_svc.get("auto_assign_persist") == "MAYBE"
        display_state = cfg_svc.get_preset_display_state(readonly=True)
        current_config_state = dict(display_state.get("current_config_state") or {})
        assert current_config_state["state"] == "degraded"
        assert current_config_state["baseline_source"] == "unknown"
        assert current_config_state["provenance_missing"] is True
        assert current_config_state["repair_notice"]["kind"] == "none"
    finally:
        conn.close()


def test_config_service_page_save_hidden_repair_with_missing_reason_stays_blocked() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        conn.execute("DELETE FROM ScheduleConfig WHERE config_key = ?", (cfg_svc.ACTIVE_PRESET_REASON_KEY,))
        conn.commit()

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                "auto_assign_persist",
                "MAYBE",
                description=cfg_svc._field_description("auto_assign_persist"),
            )

        saved = cfg_svc.save_page_config(
            {
                "sort_strategy": "priority_first",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "holiday_default_efficiency": "0.8",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "no",
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "greedy",
                "objective": "min_overdue",
                "time_budget_seconds": "20",
                "freeze_window_enabled": "no",
                "freeze_window_days": "0",
            }
        )

        remaining_reason = conn.execute(
            "SELECT COUNT(1) FROM ScheduleConfig WHERE config_key = ?",
            (cfg_svc.ACTIVE_PRESET_REASON_KEY,),
        ).fetchone()[0]
        display_state = cfg_svc.get_preset_display_state(readonly=True)
        current_config_state = dict(display_state.get("current_config_state") or {})

        assert saved.hidden_repaired_fields == []
        assert saved.blocked_hidden_repairs == ["auto_assign_persist"]
        assert saved.status == "blocked_hidden_repair"
        assert saved.normalized_snapshot.auto_assign_persist == "yes"
        assert any(event.get("field") == "auto_assign_persist" for event in saved.effective_snapshot.degradation_events)
        assert cfg_svc.get("auto_assign_persist") == "MAYBE"
        assert display_state["active_preset"] == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert display_state["active_preset_reason"] is None
        assert display_state["active_preset_reason_missing"] is True
        assert int(remaining_reason or 0) == 0
        assert current_config_state["state"] != "exact"
        assert current_config_state["provenance_missing"] is True
    finally:
        conn.close()


def test_config_service_page_save_visible_change_marks_custom_manual() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        saved = cfg_svc.save_preset("current-demo")
        assert saved["effective_active_preset"] == "current-demo"

        cfg_svc.save_page_config(
            {
                "sort_strategy": "due_date_first",
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "holiday_default_efficiency": "0.8",
                "prefer_primary_skill": "no",
                "enforce_ready_default": "no",
                "dispatch_mode": "batch_order",
                "dispatch_rule": "slack",
                "auto_assign_enabled": "no",
                "ortools_enabled": "no",
                "ortools_time_limit_seconds": "5",
                "algo_mode": "greedy",
                "objective": "min_overdue",
                "time_budget_seconds": "20",
                "freeze_window_enabled": "no",
                "freeze_window_days": "3",
            }
        )

        assert cfg_svc.get_active_preset() == cfg_svc.ACTIVE_PRESET_CUSTOM
        assert cfg_svc.get_active_preset_reason() == cfg_svc.ACTIVE_PRESET_REASON_MANUAL
    finally:
        conn.close()


def test_config_service_save_preset_rejects_strict_dirty_hidden_config() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                "auto_assign_persist",
                "MAYBE",
                description=cfg_svc._field_description("auto_assign_persist"),
            )

        rejected = cfg_svc.save_preset("dirty-demo")
        assert rejected["status"] == "rejected"
        assert rejected["requested_preset"] == "dirty-demo"
        assert rejected["effective_active_preset"] == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert rejected["error_field"] == "auto_assign_persist"
        assert rejected["error_fields"] == ["auto_assign_persist"]
        assert rejected["error_message"]
        assert cfg_svc.repo.get_value(cfg_svc._preset_key("dirty-demo"), default=None) is None
        assert cfg_svc.get_active_preset() == cfg_svc.BUILTIN_PRESET_DEFAULT
    finally:
        conn.close()


def test_config_service_save_preset_rejected_path_does_not_materialize_provenance_rows() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        builtin_keys = [cfg_svc._preset_key(name) for name, _snapshot, _description in cfg_svc._builtin_presets()]
        watched_keys = ["objective", cfg_svc.ACTIVE_PRESET_KEY, cfg_svc.ACTIVE_PRESET_REASON_KEY, *builtin_keys]
        placeholders = ", ".join("?" for _ in watched_keys)

        conn.execute(
            f"DELETE FROM ScheduleConfig WHERE config_key IN ({placeholders})",
            watched_keys,
        )
        conn.commit()

        rejected = cfg_svc.save_preset("dirty-demo")
        remaining = {
            row["config_key"]
            for row in conn.execute(
                f"SELECT config_key FROM ScheduleConfig WHERE config_key IN ({placeholders})",
                watched_keys,
            ).fetchall()
        }

        assert rejected["status"] == "rejected"
        assert rejected["requested_preset"] == "dirty-demo"
        assert cfg_svc.repo.get_value(cfg_svc._preset_key("dirty-demo"), default=None) is None
        assert remaining == set(), remaining
    finally:
        conn.close()


def test_config_service_save_preset_rejected_path_with_missing_reason_does_not_claim_named_provenance() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        conn.execute("DELETE FROM ScheduleConfig WHERE config_key = ?", (cfg_svc.ACTIVE_PRESET_REASON_KEY,))
        conn.commit()

        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                "auto_assign_persist",
                "MAYBE",
                description=cfg_svc._field_description("auto_assign_persist"),
            )

        rejected = cfg_svc.save_preset("dirty-demo")
        display_state = cfg_svc.get_preset_display_state(readonly=True)

        assert rejected["status"] == "rejected"
        assert rejected["requested_preset"] == "dirty-demo"
        assert rejected["effective_active_preset"] == cfg_svc.ACTIVE_PRESET_CUSTOM
        assert rejected["reason"] is None
        assert rejected["error_field"] == "auto_assign_persist"
        assert rejected["error_fields"] == ["auto_assign_persist"]
        assert cfg_svc.repo.get_value(cfg_svc._preset_key("dirty-demo"), default=None) is None
        assert display_state["active_preset"] == cfg_svc.BUILTIN_PRESET_DEFAULT
        assert display_state["active_preset_reason_missing"] is True
        assert display_state["current_config_state"]["provenance_missing"] is True
    finally:
        conn.close()


def test_config_service_apply_preset_rejected_path_does_not_materialize_provenance_rows() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        payload = cfg_svc.get_snapshot().to_dict()
        payload.pop("priority_weight", None)
        payload.pop("due_weight", None)
        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                cfg_svc._preset_key("缺省字段方案"),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                description="regression preset",
            )

        builtin_keys = [cfg_svc._preset_key(name) for name, _snapshot, _description in cfg_svc._builtin_presets()]
        watched_keys = [cfg_svc.ACTIVE_PRESET_KEY, cfg_svc.ACTIVE_PRESET_REASON_KEY, *builtin_keys]
        placeholders = ", ".join("?" for _ in watched_keys)

        conn.execute(
            f"DELETE FROM ScheduleConfig WHERE config_key IN ({placeholders})",
            watched_keys,
        )
        conn.commit()

        before = cfg_svc.get_snapshot(strict_mode=True).to_dict()
        applied = cfg_svc.apply_preset("缺省字段方案")
        after = cfg_svc.get_snapshot(strict_mode=True).to_dict()
        remaining = {
            row["config_key"]
            for row in conn.execute(
                f"SELECT config_key FROM ScheduleConfig WHERE config_key IN ({placeholders})",
                watched_keys,
            ).fetchall()
        }

        assert applied["status"] == "rejected"
        assert applied["requested_preset"] == "缺省字段方案"
        assert applied["effective_active_preset"] in {"", cfg_svc.ACTIVE_PRESET_CUSTOM}
        assert applied["error_fields"] == ["priority_weight", "due_weight"]
        assert remaining == set(), remaining
        assert after == before
    finally:
        conn.close()


def test_config_service_apply_preset_rejected_with_missing_reason_does_not_claim_named_provenance() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()

        payload = cfg_svc.get_snapshot().to_dict()
        payload.pop("priority_weight", None)
        payload.pop("due_weight", None)
        with cfg_svc.tx_manager.transaction():
            cfg_svc.repo.set(
                cfg_svc._preset_key("缺省字段方案"),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                description="regression preset",
            )

        conn.execute("DELETE FROM ScheduleConfig WHERE config_key = ?", (cfg_svc.ACTIVE_PRESET_REASON_KEY,))
        conn.commit()

        before = cfg_svc.get_snapshot(strict_mode=True).to_dict()
        applied = cfg_svc.apply_preset("缺省字段方案")
        after = cfg_svc.get_snapshot(strict_mode=True).to_dict()
        remaining_reason = conn.execute(
            "SELECT COUNT(1) FROM ScheduleConfig WHERE config_key = ?",
            (cfg_svc.ACTIVE_PRESET_REASON_KEY,),
        ).fetchone()[0]

        assert applied["status"] == "rejected"
        assert applied["requested_preset"] == "缺省字段方案"
        assert applied["effective_active_preset"] == cfg_svc.ACTIVE_PRESET_CUSTOM
        assert applied["reason"] is None
        assert applied["error_fields"] == ["priority_weight", "due_weight"]
        assert int(remaining_reason or 0) == 0
        assert after == before
    finally:
        conn.close()

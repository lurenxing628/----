from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.services.common.safe_logging import safe_warning

from .active_preset_service import ActivePresetService
from .active_preset_state import HiddenRepairDecision, PageSaveProvenanceState
from .config_bootstrap_service import ConfigBootstrapService
from .config_constants import (
    ACTIVE_PRESET_CUSTOM,
    ACTIVE_PRESET_KEY,
    ACTIVE_PRESET_META_KEY,
    ACTIVE_PRESET_META_REASON_HIDDEN_REPAIR,
    ACTIVE_PRESET_META_REASON_MANUAL,
    ACTIVE_PRESET_META_REASON_VISIBLE_REPAIR,
    ACTIVE_PRESET_REASON_KEY,
    ACTIVE_PRESET_REASON_MANUAL,
    ACTIVE_PRESET_REASON_PRESET_ADJUSTED,
    ACTIVE_PRESET_REASON_PRESET_MISMATCH,
    ACTIVE_PRESET_REASON_VISIBLE_REPAIR,
    CONFIG_PAGE_FIELDS,
)
from .config_field_spec import list_config_fields
from .config_page_outcome import ConfigPageSaveOutcome
from .config_page_save_policy import ConfigPageSavePolicy
from .config_page_write_plan import ConfigPageWritePlan
from .config_read_service import ConfigReadService
from .config_snapshot import ScheduleConfigSnapshot, ensure_schedule_config_snapshot
from .config_uow import ConfigWriteUnitOfWork
from .config_write_service import ConfigFieldMutationService


class ConfigPageSaveService(ConfigPageSavePolicy):
    def __init__(
        self,
        *,
        uow: ConfigWriteUnitOfWork,
        active_service: ActivePresetService,
        read_service: ConfigReadService,
        mutation_service: ConfigFieldMutationService,
        bootstrap_service: ConfigBootstrapService,
    ) -> None:
        self.uow = uow
        self.active_service = active_service
        self.read_service = read_service
        self.mutation_service = mutation_service
        self.bootstrap_service = bootstrap_service

    def normalize_payload(
        self,
        form_values: Any,
        *,
        current_snapshot: ScheduleConfigSnapshot,
        submitted_fields: set[str],
    ) -> ScheduleConfigSnapshot:
        payload = current_snapshot.to_dict()
        for key in CONFIG_PAGE_FIELDS:
            if key in submitted_fields:
                payload[key] = self.form_value(form_values, key)

        priority_raw = self.form_value(form_values, "priority_weight") if "priority_weight" in submitted_fields else None
        due_raw = self.form_value(form_values, "due_weight") if "due_weight" in submitted_fields else None
        priority_weight, due_weight, ready_weight = self.normalize_page_weights(
            priority_raw,
            due_raw,
            current_snapshot,
        )
        payload["priority_weight"] = float(priority_weight)
        payload["due_weight"] = float(due_weight)
        payload["ready_weight"] = float(ready_weight)

        return ensure_schedule_config_snapshot(
            payload,
            strict_mode=True,
            source="scheduler.config_service.save_page_config",
        )

    def current_provenance_state(self, *, current_snapshot: ScheduleConfigSnapshot) -> PageSaveProvenanceState:
        return self.read_service.get_page_save_provenance_state(current_snapshot=current_snapshot)

    def hidden_repair_decision(
        self,
        *,
        fields: List[str],
        current_active_preset: Optional[str],
        provenance_state: PageSaveProvenanceState,
    ) -> HiddenRepairDecision:
        if not fields:
            return HiddenRepairDecision(allowed=True, fields=[])
        current_state = provenance_state.current_config_state
        if not current_active_preset or current_state.provenance_missing:
            return HiddenRepairDecision(False, list(fields), "blocked_provenance_missing")
        if current_state.baseline_probe_failed:
            return HiddenRepairDecision(False, list(fields), "blocked_baseline_unverifiable")
        if current_state.baseline_diff_fields:
            return HiddenRepairDecision(False, list(fields), "blocked_baseline_drifted")
        if not provenance_state.can_preserve_named_provenance_for_write:
            status = str(provenance_state.provenance_completeness_status or "")
            return HiddenRepairDecision(
                False,
                list(fields),
                "blocked_custom_reason_missing" if status == "custom_reason_blank" else "blocked_adjusted_preset",
            )
        return HiddenRepairDecision(True, list(fields))

    def initial_write_plan(
        self,
        *,
        write_values: Dict[str, Any],
        current_active_preset: Optional[str],
        current_active_preset_reason: Optional[str],
        hidden_repaired_fields: List[str],
    ) -> Tuple[ConfigPageWritePlan, Optional[Dict[str, Any]], Optional[str]]:
        hidden_notice = self.hidden_repair_notice(hidden_repaired_fields) if hidden_repaired_fields else None
        hidden_reason = hidden_notice["message"] if hidden_notice is not None else None
        plan = ConfigPageWritePlan(
            updates=self.mutation_service.registered_updates(write_values),
            hidden_repaired_fields=list(hidden_repaired_fields),
            notices=self.notices(hidden_notice),
            active_preset_after=current_active_preset,
            active_preset_reason_after=current_active_preset_reason,
        )
        return plan, hidden_notice, hidden_reason

    def apply_visible_change_plan(self, *, plan: ConfigPageWritePlan, hidden_repair_notice: Optional[Dict[str, Any]]) -> None:
        repair_notices = [hidden_repair_notice] if hidden_repair_notice is not None else []
        plan.updates.extend(
            self.active_service.active_preset_updates(
                ACTIVE_PRESET_CUSTOM,
                reason=ACTIVE_PRESET_REASON_MANUAL,
                meta=self.active_service.meta_payload(
                    reason_code=ACTIVE_PRESET_META_REASON_MANUAL,
                    repair_notices=repair_notices,
                ),
            )
        )
        plan.active_preset_after = ACTIVE_PRESET_CUSTOM
        plan.active_preset_reason_after = ACTIVE_PRESET_REASON_MANUAL

    def apply_visible_repair_plan(self, *, plan: ConfigPageWritePlan, hidden_repair_notice: Optional[Dict[str, Any]]) -> None:
        repair_notices = [self.visible_repair_notice()]
        if hidden_repair_notice is not None:
            repair_notices.append(hidden_repair_notice)
        plan.updates.extend(
            self.active_service.active_preset_updates(
                ACTIVE_PRESET_CUSTOM,
                reason=ACTIVE_PRESET_REASON_VISIBLE_REPAIR,
                meta=self.active_service.meta_payload(
                    reason_code=ACTIVE_PRESET_META_REASON_VISIBLE_REPAIR,
                    repair_notices=repair_notices,
                ),
            )
        )
        plan.active_preset_after = ACTIVE_PRESET_CUSTOM
        plan.active_preset_reason_after = ACTIVE_PRESET_REASON_VISIBLE_REPAIR

    def apply_hidden_repair_plan(
        self,
        *,
        plan: ConfigPageWritePlan,
        current_active_preset: str,
        current_active_preset_reason: Optional[str],
        current_active_preset_meta: Optional[Dict[str, Any]],
        hidden_repair_reason: Optional[str],
        hidden_repair_notice: Optional[Dict[str, Any]],
    ) -> None:
        current_reason = str(current_active_preset_reason or "").strip()
        preserved_named_reason = ConfigReadService.reason_in(
            current_reason,
            ACTIVE_PRESET_REASON_PRESET_ADJUSTED,
            ACTIVE_PRESET_REASON_PRESET_MISMATCH,
        )
        preserved_custom_reason = current_active_preset == ACTIVE_PRESET_CUSTOM and bool(current_reason)
        if preserved_named_reason or preserved_custom_reason:
            current_meta = self.active_service.meta_from_value(
                current_active_preset_meta,
                reason_fallback=current_active_preset_reason,
            )
            repair_notices = list(current_meta.get("repair_notices") or [])
            if hidden_repair_notice is not None:
                repair_notices.append(hidden_repair_notice)
            reason_after = current_reason or None
            hidden_meta = self.active_service.meta_payload(
                reason_code=current_meta.get("reason_code"),
                repair_notices=repair_notices,
            )
        else:
            reason_after = hidden_repair_reason
            hidden_meta = self.active_service.meta_payload(
                reason_code=ACTIVE_PRESET_META_REASON_HIDDEN_REPAIR,
                repair_notices=[hidden_repair_notice] if hidden_repair_notice is not None else [],
            )
        plan.updates.extend(
            self.active_service.active_preset_updates(
                current_active_preset,
                reason=reason_after,
                meta=hidden_meta,
            )
        )
        plan.active_preset_after = current_active_preset
        plan.active_preset_reason_after = reason_after

    def build_write_plan(
        self,
        *,
        write_values: Dict[str, Any],
        visible_changed_fields: List[str],
        visible_repaired_fields: List[str],
        hidden_repaired_fields: List[str],
        current_active_preset: Optional[str],
        current_active_preset_reason: Optional[str],
        current_active_preset_meta: Optional[Dict[str, Any]],
        provenance_state: PageSaveProvenanceState,
    ) -> ConfigPageWritePlan:
        decision = self.hidden_repair_decision(
            fields=hidden_repaired_fields,
            current_active_preset=current_active_preset,
            provenance_state=provenance_state,
        )
        blocked_hidden_notice: Optional[Dict[str, Any]] = None
        if not decision.allowed:
            blocked_hidden_notice = self.blocked_hidden_repair_notice(
                decision.fields,
                block_reason=decision.block_reason,
            )
            write_values = dict(write_values)
            for key in decision.fields:
                write_values.pop(key, None)
            hidden_repaired_fields = []

        plan, hidden_notice, hidden_reason = self.initial_write_plan(
            write_values=write_values,
            current_active_preset=current_active_preset,
            current_active_preset_reason=current_active_preset_reason,
            hidden_repaired_fields=hidden_repaired_fields,
        )
        if not decision.allowed:
            plan.blocked_hidden_repairs = list(decision.fields)
            plan.notices = self.notices(*plan.notices, blocked_hidden_notice)
        if visible_changed_fields:
            self.apply_visible_change_plan(plan=plan, hidden_repair_notice=hidden_notice)
            return plan
        if visible_repaired_fields:
            self.apply_visible_repair_plan(plan=plan, hidden_repair_notice=hidden_notice)
            return plan
        if not hidden_repaired_fields:
            return plan
        if current_active_preset and decision.allowed:
            self.apply_hidden_repair_plan(
                plan=plan,
                current_active_preset=current_active_preset,
                current_active_preset_reason=current_active_preset_reason,
                current_active_preset_meta=current_active_preset_meta,
                hidden_repair_reason=hidden_reason,
                hidden_repair_notice=hidden_notice,
            )
        return plan

    def raw_persisted_state(self) -> Tuple[Dict[str, Any], List[str]]:
        rows = self.uow.repo.list_all()
        by_key = {str(getattr(row, "config_key", "") or ""): row for row in rows}
        keys = [spec.key for spec in list_config_fields()]
        keys.extend([ACTIVE_PRESET_KEY, ACTIVE_PRESET_REASON_KEY, ACTIVE_PRESET_META_KEY])
        raw_values: Dict[str, Any] = {}
        missing: List[str] = []
        seen = set()
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            row = by_key.get(key)
            if row is None:
                missing.append(key)
                continue
            raw_values[key] = getattr(row, "config_value", None)
        return raw_values, missing

    def save_page_config(self, form_values: Any) -> ConfigPageSaveOutcome:
        self.bootstrap_service.ensure_defaults_if_pristine()
        active_meta_raw = self.uow.repo.get_value(ACTIVE_PRESET_META_KEY, default=None)
        meta_parse_warning = self.active_service.meta_parse_warning(active_meta_raw)
        if meta_parse_warning:
            safe_warning(self.uow.logger, str(meta_parse_warning["message"]))
        current_snapshot = self.read_service.get_snapshot(strict_mode=False)
        provenance_state = self.current_provenance_state(current_snapshot=current_snapshot)
        current_active_preset = str(provenance_state.active_preset or "").strip() or None
        current_active_reason = str(provenance_state.active_preset_reason or "").strip() or None
        current_active_meta = dict(provenance_state.active_preset_meta or {})
        submitted = self.submitted_fields(form_values)
        normalized_snapshot = self.normalize_payload(
            form_values,
            current_snapshot=current_snapshot,
            submitted_fields=submitted,
        )
        write_values = self.write_values(normalized_snapshot, submitted_fields=submitted)
        visible_changed = self.visible_changed_fields(current_snapshot=current_snapshot, write_values=write_values)
        visible_repaired = self.visible_repair_fields(current_snapshot=current_snapshot, write_values=write_values)
        hidden_values = self.hidden_repair_values(
            current_snapshot=current_snapshot,
            normalized_snapshot=normalized_snapshot,
        )
        hidden_repaired = list(hidden_values.keys())
        write_values.update(hidden_values)
        materialized = self.materialized_write_values(
            current_snapshot=current_snapshot,
            write_values=write_values,
        )
        plan = self.build_write_plan(
            write_values=materialized,
            visible_changed_fields=visible_changed,
            visible_repaired_fields=visible_repaired,
            hidden_repaired_fields=hidden_repaired,
            current_active_preset=current_active_preset,
            current_active_preset_reason=current_active_reason,
            current_active_preset_meta=current_active_meta,
            provenance_state=provenance_state,
        )
        if plan.updates:
            with self.uow.tx_manager.transaction():
                self.uow.repo.set_batch(plan.updates)
        post_save_snapshot = self.read_service.get_snapshot(strict_mode=False)
        raw_values, raw_missing = self.raw_persisted_state()
        return ConfigPageSaveOutcome(
            snapshot=post_save_snapshot,
            status=self.save_status(plan),
            normalized_snapshot=normalized_snapshot,
            raw_persisted_values=raw_values,
            raw_missing_fields=raw_missing,
            meta_parse_warnings=[meta_parse_warning] if meta_parse_warning else [],
            visible_changed_fields=list(visible_changed),
            visible_repaired_fields=list(visible_repaired),
            hidden_repaired_fields=list(plan.hidden_repaired_fields),
            blocked_hidden_repairs=list(plan.blocked_hidden_repairs),
            notices=list(plan.notices),
            active_preset_after=plan.active_preset_after,
            active_preset_reason_after=plan.active_preset_reason_after,
        )


__all__ = ["ConfigPageSaveService"]

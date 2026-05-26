from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

_TRUSTED_ROW_SOURCE_TABLES = frozenset(
    (
        "schedule",
        "candidate_rows",
        "adjustment_scenario_rows",
        "batches",
        "batch_materials",
        "machine_downtimes",
    )
)


@dataclass(frozen=True)
class PlanIdentity:
    version: Optional[int]
    requested_plan_role: Optional[str]
    effective_plan_role: str
    plan_resolution_status: str
    source_table: str
    source_row_id: Optional[int]
    candidate_id: Optional[int]
    candidate_key: Optional[str]
    scenario_id: Optional[str]
    schedule_result_status: Optional[str]
    is_simulation: bool
    label: str
    user_label: str
    is_official: bool
    is_preview: bool
    is_current_executable_version: bool
    is_current_executable_official_version: bool
    is_superseded_by_newer_version: bool
    schedule_lock_status: Optional[str]
    can_dispatch: bool
    can_write_feedback: bool
    detail_saved: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "requested_plan_role": self.requested_plan_role,
            "effective_plan_role": self.effective_plan_role,
            "plan_resolution_status": self.plan_resolution_status,
            "source_table": self.source_table,
            "source_row_id": self.source_row_id,
            "candidate_id": self.candidate_id,
            "candidate_key": self.candidate_key,
            "scenario_id": self.scenario_id,
            "schedule_result_status": self.schedule_result_status,
            "is_simulation": bool(self.is_simulation),
            "label": self.label,
            "user_label": self.user_label,
            "is_official": bool(self.is_official),
            "is_preview": bool(self.is_preview),
            "is_current_executable_version": bool(self.is_current_executable_version),
            "is_current_executable_official_version": bool(self.is_current_executable_official_version),
            "is_superseded_by_newer_version": bool(self.is_superseded_by_newer_version),
            "schedule_lock_status": self.schedule_lock_status,
            "can_dispatch": bool(self.can_dispatch),
            "can_write_feedback": bool(self.can_write_feedback),
            "detail_saved": bool(self.detail_saved),
        }


@dataclass(frozen=True)
class EvidenceLink:
    evidence_type: str
    evidence_label: str
    object_type: str
    object_id: Optional[Any]
    plan_identity: PlanIdentity
    source_table: Optional[str]
    source_row_id: Optional[Any]
    evidence_scope: str
    aggregation_key: Optional[str] = None
    contributing_count: Optional[int] = None
    missing_data_key: Optional[str] = None
    expected_source: Optional[str] = None
    checked_object_type: Optional[str] = None
    checked_object_id: Optional[Any] = None
    checked_range_start: Optional[Any] = None
    checked_range_end: Optional[Any] = None
    checked_at: Optional[Any] = None
    gap_label: Optional[str] = None
    source_version: Optional[int] = None
    candidate_id: Optional[int] = None
    scenario_id: Optional[str] = None
    metric_name: Optional[str] = None
    metric_value: Optional[Any] = None
    time_range_start: Optional[Any] = None
    time_range_end: Optional[Any] = None
    source_page: str = ""
    link: Optional[str] = None
    confidence: str = "fact"

    def validate(self) -> None:
        self._validate_link_identity()
        self._validate_source_table()
        if self.evidence_scope == "row":
            if not self.source_table or self.source_row_id is None:
                raise ValueError("行级证据必须带来源表和来源行。")
            return
        if self.evidence_scope == "aggregate":
            if not self.aggregation_key or self.contributing_count is None:
                raise ValueError("汇总证据必须带汇总口径和参与数量。")
            return
        if self.evidence_scope == "missing_data":
            if self.confidence != "missing_data":
                raise ValueError("缺数据证据必须标成当前数据不足。")
            missing_required = (
                self.missing_data_key,
                self.expected_source,
                self.checked_object_type,
                self.checked_object_id,
                self.checked_at,
                self.gap_label,
            )
            if any(value is None or str(value).strip() == "" for value in missing_required):
                raise ValueError("缺数据证据必须写清缺什么、查过哪里、影响谁和检查时间。")
            return
        raise ValueError("证据范围必须是 row、aggregate 或 missing_data。")

    def _validate_source_table(self) -> None:
        if self.source_table and self.source_table not in _TRUSTED_ROW_SOURCE_TABLES:
            raise ValueError("证据来源表不可信，不能作为诊断依据。")

    def _validate_link_identity(self) -> None:
        if not self.link:
            return
        query = parse_qs(urlparse(str(self.link)).query, keep_blank_values=True)
        self._require_single_link_value(
            query,
            "version",
            None if self.plan_identity.version is None else str(self.plan_identity.version),
            "证据链接必须带当前计划版本。",
        )
        self._require_single_link_value(
            query,
            "plan_role",
            self.plan_identity.requested_plan_role,
            "证据链接必须带当前方案。",
        )
        self._require_single_link_value(
            query,
            "scenario_id",
            self.plan_identity.scenario_id,
            "证据链接必须带当前模拟预览。",
        )

    def _require_single_link_value(
        self,
        query: Dict[str, Any],
        key: str,
        expected: Optional[str],
        message: str,
    ) -> None:
        values = query.get(key) or []
        normalized = [str(value).strip() for value in values]
        if expected is None or str(expected).strip() == "":
            if normalized:
                raise ValueError(message)
            return
        if normalized != [str(expected).strip()]:
            raise ValueError(message)

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "evidence_type": self.evidence_type,
            "evidence_label": self.evidence_label,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "plan_identity": self.plan_identity.to_dict(),
            "source_table": self.source_table,
            "source_row_id": self.source_row_id,
            "evidence_scope": self.evidence_scope,
            "aggregation_key": self.aggregation_key,
            "contributing_count": self.contributing_count,
            "missing_data_key": self.missing_data_key,
            "expected_source": self.expected_source,
            "checked_object_type": self.checked_object_type,
            "checked_object_id": self.checked_object_id,
            "checked_range_start": self.checked_range_start,
            "checked_range_end": self.checked_range_end,
            "checked_at": self.checked_at,
            "gap_label": self.gap_label,
            "source_version": self.source_version,
            "candidate_id": self.candidate_id,
            "scenario_id": self.scenario_id,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "time_range_start": self.time_range_start,
            "time_range_end": self.time_range_end,
            "source_page": self.source_page,
            "link": self.link,
            "confidence": self.confidence,
        }


__all__ = ["EvidenceLink", "PlanIdentity"]

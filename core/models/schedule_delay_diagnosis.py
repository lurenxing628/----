from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.models.schedule_plan_identity import EvidenceLink, PlanIdentity


@dataclass(frozen=True)
class ConfirmedFact:
    text: str
    evidences: List[EvidenceLink]

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "evidences": [item.to_dict() for item in self.evidences]}


@dataclass(frozen=True)
class DiagnosisClue:
    clue_code: str
    clue_label: str
    plain_text: str
    confidence: str
    evidences: List[EvidenceLink]
    data_gaps: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clue_code": self.clue_code,
            "clue_label": self.clue_label,
            "plain_text": self.plain_text,
            "confidence": self.confidence,
            "evidences": [item.to_dict() for item in self.evidences],
            "data_gaps": list(self.data_gaps),
        }


@dataclass(frozen=True)
class SuggestedAction:
    label: str
    target_page: str
    link: Optional[str]
    reason: str
    priority: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "target_page": self.target_page,
            "link": self.link,
            "reason": self.reason,
            "priority": self.priority,
        }


@dataclass(frozen=True)
class OperationClue:
    op_id: Optional[int]
    op_name: Optional[str]
    batch_id: str
    machine_id: Optional[str]
    operator_id: Optional[str]
    planned_start_time: Optional[str]
    planned_end_time: Optional[str]
    actual_start_time: Optional[str]
    actual_end_time: Optional[str]
    clue_label: str
    evidences: List[EvidenceLink]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op_id": self.op_id,
            "op_name": self.op_name,
            "batch_id": self.batch_id,
            "machine_id": self.machine_id,
            "operator_id": self.operator_id,
            "planned_start_time": self.planned_start_time,
            "planned_end_time": self.planned_end_time,
            "actual_start_time": self.actual_start_time,
            "actual_end_time": self.actual_end_time,
            "clue_label": self.clue_label,
            "evidences": [item.to_dict() for item in self.evidences],
        }


@dataclass(frozen=True)
class DiagnosisTraceMeta:
    generated_at: str
    as_of_time: str
    plan_identity: PlanIdentity
    evidence_count: int
    evidence_sources: List[str]
    rule_version: str
    ranking_inputs: List[str]
    clue_selection_trace: List[str]
    input_fingerprint: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "as_of_time": self.as_of_time,
            "plan_identity": self.plan_identity.to_dict(),
            "evidence_count": int(self.evidence_count),
            "evidence_sources": list(self.evidence_sources),
            "rule_version": self.rule_version,
            "ranking_inputs": list(self.ranking_inputs),
            "clue_selection_trace": list(self.clue_selection_trace),
            "input_fingerprint": self.input_fingerprint,
        }


@dataclass(frozen=True)
class OverdueDiagnosisItem:
    batch_id: str
    part_no: Optional[str]
    part_name: Optional[str]
    due_date: Optional[str]
    bucket: str
    delay_hours: float
    delay_days: float
    finish_time: Optional[str]
    as_of_time: str
    suggested_operation_clue: Optional[OperationClue]
    last_operation: Optional[OperationClue]
    confirmed_facts: List[ConfirmedFact]
    candidate_clues: List[DiagnosisClue]
    leading_clue_code: str
    leading_clue_label: str
    confidence: str
    evidences: List[EvidenceLink]
    data_gaps: List[str]
    suggested_actions: List[SuggestedAction]
    links: List[EvidenceLink]
    trace_meta: DiagnosisTraceMeta

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "part_no": self.part_no,
            "part_name": self.part_name,
            "due_date": self.due_date,
            "bucket": self.bucket,
            "delay_hours": self.delay_hours,
            "delay_days": self.delay_days,
            "finish_time": self.finish_time,
            "as_of_time": self.as_of_time,
            "suggested_operation_clue": self.suggested_operation_clue.to_dict() if self.suggested_operation_clue else None,
            "last_operation": self.last_operation.to_dict() if self.last_operation else None,
            "confirmed_facts": [item.to_dict() for item in self.confirmed_facts],
            "candidate_clues": [item.to_dict() for item in self.candidate_clues],
            "leading_clue_code": self.leading_clue_code,
            "leading_clue_label": self.leading_clue_label,
            "confidence": self.confidence,
            "evidences": [item.to_dict() for item in self.evidences],
            "data_gaps": list(self.data_gaps),
            "suggested_actions": [item.to_dict() for item in self.suggested_actions],
            "links": [item.to_dict() for item in self.links],
            "trace_meta": self.trace_meta.to_dict(),
        }


@dataclass(frozen=True)
class OverdueDiagnosisReport:
    plan_identity: PlanIdentity
    generated_at: str
    as_of_time: str
    total_count: int
    scheduled_count: int
    unscheduled_count: int
    invalid_time_count: int
    top_clues: List[Dict[str, Any]]
    items: List[OverdueDiagnosisItem]
    warnings: List[str]
    trace_meta: DiagnosisTraceMeta

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_identity": self.plan_identity.to_dict(),
            "generated_at": self.generated_at,
            "as_of_time": self.as_of_time,
            "total_count": int(self.total_count),
            "scheduled_count": int(self.scheduled_count),
            "unscheduled_count": int(self.unscheduled_count),
            "invalid_time_count": int(self.invalid_time_count),
            "top_clues": [dict(item) for item in self.top_clues],
            "items": [item.to_dict() for item in self.items],
            "warnings": list(self.warnings),
            "trace_meta": self.trace_meta.to_dict(),
        }


__all__ = [
    "ConfirmedFact",
    "DiagnosisClue",
    "DiagnosisTraceMeta",
    "OperationClue",
    "OverdueDiagnosisItem",
    "OverdueDiagnosisReport",
    "SuggestedAction",
]

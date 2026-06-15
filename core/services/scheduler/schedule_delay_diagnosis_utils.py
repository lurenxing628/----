from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from core.models.schedule_delay_diagnosis import DiagnosisTraceMeta, OverdueDiagnosisItem
from core.models.schedule_plan_identity import EvidenceLink, PlanIdentity

RULE_VERSION = "delay-diagnosis-v1"


def text(value: Any) -> str:
    return str(value or "").strip()


def float_or_default(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def stable_unique(values: Iterable[Any]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for value in values:
        item = text(value)
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def plan_link(plan_identity: PlanIdentity, target: str, *, scenario_id: Optional[str] = None) -> str:
    # scenario_id 有意不写入链接：它是内部计划身份，URL 上下文改由不透明的 plan_context_token
    # 承载（见 web 层），契约亦钉死 scenario_id 不得出现在诊断深链中。保留形参仅为兼容既有
    # 调用签名、让调用方显式表达“该链接处于某模拟方案上下文”，函数体不再消费它。
    _ = scenario_id
    parts = [
        f"version={plan_identity.version}",
        f"plan_role={plan_identity.requested_plan_role}",
    ]
    return f"{target}?{'&'.join(parts)}"


def build_trace_meta(
    *,
    plan_identity: PlanIdentity,
    generated_at: str,
    as_of_text: str,
    evidences: Sequence[EvidenceLink],
    ranking_inputs: List[str],
    clue_selection_trace: List[str],
) -> DiagnosisTraceMeta:
    sources = stable_unique(_evidence_source_label(evidence) for evidence in evidences)
    fingerprint = input_fingerprint(
        plan_identity=plan_identity,
        as_of_text=as_of_text,
        evidences=evidences,
        ranking_inputs=ranking_inputs,
    )
    return DiagnosisTraceMeta(
        generated_at=generated_at,
        as_of_time=as_of_text,
        plan_identity=plan_identity,
        evidence_count=len(evidences),
        evidence_sources=sources,
        rule_version=RULE_VERSION,
        ranking_inputs=ranking_inputs,
        clue_selection_trace=clue_selection_trace,
        input_fingerprint=fingerprint,
    )


def _evidence_source_label(evidence: EvidenceLink) -> str:
    return text(evidence.source_table) or text(evidence.expected_source) or text(evidence.source_page)


def input_fingerprint(
    *,
    plan_identity: PlanIdentity,
    as_of_text: str,
    evidences: Sequence[EvidenceLink],
    ranking_inputs: Sequence[str],
) -> str:
    parts = [
        f"version={plan_identity.version}",
        f"role={plan_identity.requested_plan_role}",
        f"scenario={plan_identity.scenario_id or ''}",
        f"as_of={as_of_text}",
    ]
    for evidence in evidences:
        parts.append(
            f"{evidence.evidence_scope}:{evidence.source_table or ''}:"
            f"{evidence.source_row_id or ''}:{evidence.aggregation_key or evidence.missing_data_key or ''}"
        )
    parts.extend(str(item) for item in ranking_inputs)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def top_clues(items: Sequence[OverdueDiagnosisItem]) -> List[Dict[str, Any]]:
    counts: Dict[str, Dict[str, Any]] = {}
    for item in items:
        key = item.leading_clue_code
        entry = counts.setdefault(
            key,
            {
                "clue_code": key,
                "clue_label": item.leading_clue_label,
                "count": 0,
                "confidence": item.confidence,
            },
        )
        entry["count"] = int(entry["count"]) + 1
    return sorted(counts.values(), key=lambda item: (-int(item.get("count") or 0), str(item.get("clue_code") or "")))


def all_item_evidences(items: Sequence[OverdueDiagnosisItem]) -> List[EvidenceLink]:
    out: List[EvidenceLink] = []
    for item in items:
        out.extend(item.evidences)
    return out


__all__ = [
    "RULE_VERSION",
    "all_item_evidences",
    "build_trace_meta",
    "float_or_default",
    "int_or_none",
    "plan_link",
    "stable_unique",
    "text",
    "top_clues",
]

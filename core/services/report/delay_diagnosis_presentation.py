from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from core.models.schedule_delay_diagnosis import OverdueDiagnosisItem, OverdueDiagnosisReport
from core.models.schedule_plan_identity import EvidenceLink

_CONFIDENCE_LABELS = {
    "likely": "证据较充分",
    "weak": "证据较少",
    "missing_data": "当前数据不足",
}


def build_delay_diagnosis_page_context(report: OverdueDiagnosisReport) -> Dict[str, Any]:
    items = [_public_item(item) for item in report.items]
    return {
        "generated_at": report.generated_at,
        "warnings": list(report.warnings or []),
        "items_by_batch": {item["batch_id"]: item for item in items if item.get("batch_id")},
    }


def build_delay_diagnosis_export_rows(
    report: OverdueDiagnosisReport,
    *,
    filters: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, Any]]:
    filter_summary = _filter_summary(filters or {})
    rows: List[Dict[str, Any]] = []
    for item in report.items:
        public_item = _public_item(item)
        rows.append(
            {
                "diagnosis_id": _diagnosis_id(item),
                "summary": _diagnosis_summary(public_item),
                "check_info": _check_info(public_item),
                "evidence_sources": _evidence_sources(item.evidences),
                "data_gaps": _join_plain(public_item.get("data_gaps"), empty="当前没有明显证据缺口。"),
                "generated_at": item.trace_meta.generated_at,
                "filters": filter_summary,
            }
        )
    return rows


def _public_item(item: OverdueDiagnosisItem) -> Dict[str, Any]:
    data_gaps = list(item.data_gaps or [])
    for clue in item.candidate_clues or []:
        data_gaps.extend(clue.data_gaps or [])
    return {
        "batch_id": item.batch_id,
        "delay_text": _delay_text(item),
        "leading_clue_label": item.leading_clue_label or "证据不足",
        "confidence_label": _CONFIDENCE_LABELS.get(item.confidence, "证据较少"),
        "data_gaps": _stable_unique(data_gaps + _item_warnings(item)),
        "suggested_actions": [
            {
                "label": action.label,
                "reason": action.reason,
                "link": action.link,
            }
            for action in item.suggested_actions or []
        ],
    }


def _delay_text(item: OverdueDiagnosisItem) -> str:
    hours = round(float(item.delay_hours or 0.0), 2)
    days = round(float(item.delay_days or 0.0), 2)
    if item.bucket == "scheduled_overdue":
        return f"计划完成已经晚了 {hours:.2f} 小时（约 {days:.2f} 天）。"
    return f"还没有计划完成时间，截至当前已经晚了 {hours:.2f} 小时（约 {days:.2f} 天）。"


def _item_warnings(item: OverdueDiagnosisItem) -> List[str]:
    warnings = ["没有现场执行反馈时，不判断现场做慢了。"]
    material_gap = [gap for gap in item.data_gaps or [] if "物料" in str(gap)]
    if material_gap:
        warnings.append("当前物料数据不足，只提示核对物料，不判断一定是物料造成延期。")
    return _stable_unique(warnings)


def _diagnosis_id(item: OverdueDiagnosisItem) -> str:
    version = item.trace_meta.plan_identity.version
    version_text = "未知版本" if version is None else f"v{int(version)}"
    return f"延期诊断-{version_text}-{item.batch_id}"


def _diagnosis_summary(item: Mapping[str, Any]) -> str:
    parts = [
        str(item.get("delay_text") or ""),
        f"建议先复核：{str(item.get('leading_clue_label') or '证据不足')}。",
        f"证据等级：{str(item.get('confidence_label') or '证据较少')}。",
    ]
    return " ".join(part for part in parts if part.strip())


def _check_info(item: Mapping[str, Any]) -> str:
    facts = _join_plain(item.get("confirmed_facts"), empty="")
    actions = []
    for action in item.get("suggested_actions") or []:
        if isinstance(action, Mapping):
            label = str(action.get("label") or "").strip()
            reason = str(action.get("reason") or "").strip()
            if label and reason:
                actions.append(f"{label}：{reason}")
            elif label:
                actions.append(label)
    action_text = _join_plain(actions, empty="")
    return _join_plain([facts, action_text], empty="请先回页面查看这条批次的诊断详情。")


def _evidence_sources(evidences: Sequence[EvidenceLink]) -> str:
    values = []
    for evidence in evidences or []:
        page = str(evidence.source_page or "").strip()
        label = str(evidence.evidence_label or "").strip()
        if page and label:
            values.append(f"{page}：{label}")
        elif label:
            values.append(label)
        elif page:
            values.append(page)
    return _join_plain(_stable_unique(values), empty="当前没有可展示的证据来源。")


def _filter_summary(filters: Mapping[str, Any]) -> str:
    parts = []
    version = filters.get("version")
    if version not in (None, ""):
        parts.append(f"排产版本：v{int(version)}")
    plan_label = str(filters.get("plan_label") or "").strip()
    if plan_label:
        parts.append(f"排产方案：{plan_label}")
    return "；".join(parts) or "按当前导出按钮所在页面筛选。"


def _join_plain(values: Optional[Iterable[Any]], *, empty: str) -> str:
    clean = [str(value or "").strip() for value in values or []]
    clean = [value for value in clean if value]
    return "；".join(_stable_unique(clean)) if clean else empty


def _stable_unique(values: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


__all__ = ["build_delay_diagnosis_export_rows", "build_delay_diagnosis_page_context"]

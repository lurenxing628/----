"""Latest twenty eligible completed operations, median and strict relative deviation."""

from collections import Counter
from decimal import Decimal
from statistics import median

from core.models.workbench_calibration import (
    MAX_SAMPLES,
    METHOD_VERSION,
    MIN_SAMPLES,
    closed_capabilities,
    issue,
    write_blockers,
)
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint

from .calibration_samples import number


def _select_recent(samples):
    if len({row["sample_ref"] for row in samples}) != len(samples):
        raise WorkbenchCommandRejected("storage_failure", "完工记录重复，请刷新后重试；仍有问题请联系维护人员。", 500)
    eligible = sorted((row for row in samples if row["eligible"]),
                      key=lambda row: (row["confirmed_finish"], row["sample_ref"]), reverse=True)
    selected = eligible[:MAX_SAMPLES]
    selected_refs = {row["sample_ref"] for row in selected}
    for row in samples:
        row["selected"] = row["sample_ref"] in selected_refs
        if row["eligible"]:
            row["exclusion_reasons"] = [] if row["selected"] else [issue("outside_recent_20", "这条完工记录不在最近 20 条整道完工记录里。")]
    return selected, len(eligible)


def _exclusion_counts(samples):
    counts = Counter(code for row in samples for code in {reason["code"] for reason in row["exclusion_reasons"]})
    messages = {reason["code"]: reason["message"] for row in samples for reason in row["exclusion_reasons"]}
    return [{"code": code, "message": messages[code], "count": count} for code, count in sorted(counts.items())]


def summarize_samples(samples):
    selected, eligible_count = _select_recent(samples)
    values = [Decimal(str(row["effective_processing_hours"])) / Decimal(row["completed_quantity"]) for row in selected]
    suggested = median(values) if len(values) >= MIN_SAMPLES else None
    return {"sample_count": len(selected), "eligible_sample_count": eligible_count, "candidate_count": len(samples),
            "excluded_count": len(samples) - len(selected), "sample_refs": [row["sample_ref"] for row in selected],
            "sample_revisions": [{"sample_ref": row["sample_ref"], "sample_revision": row["sample_revision"],
                                  "template_revision": row["template_revision"], "report_revision_refs": row["report_revision_refs"]}
                                 for row in selected],
            "suggested_unit_hours": float(suggested) if suggested is not None else None,
            "exclusion_reasons": _exclusion_counts(samples)}


def _deviation(old, suggested):
    deviation = (suggested - old) / old * 100 if old and suggested is not None else None
    finite_deviation = deviation is not None and abs(deviation) <= Decimal("1.7976931348623157e308")
    basis = "old_unknown" if old is None else "old_zero" if not old else "suggestion_unavailable" if suggested is None else "relative"
    if deviation is not None and not finite_deviation:
        basis = "not_representable"
    percent = float(deviation) if finite_deviation and deviation is not None else None
    return {"deviation_percent": percent, "absolute_deviation_percent": abs(percent) if percent is not None else None,
            "deviation_basis": basis, "over_20_percent": bool(deviation is not None and abs(deviation) > 20)}


def build_suggestion(template, summary, *, generated_at):
    old, suggested = number(template.old_unit_hours), number(summary["suggested_unit_hours"])
    reasons = write_blockers()
    if suggested is None:
        reasons.append(issue("insufficient_samples", "这个模板版本下可用的完工记录不足 5 条，暂时不给建议值。"))
    if template.source != "internal":
        reasons.append(issue("processing_basis_unconfirmed", "当前模板不是已确认的自制加工工序。"))
    return {"suggestion_ref": template.operation_ref, "operation_ref": template.operation_ref,
            "template_operation_ref": template.operation_ref, "template_revision": template.revision,
            "template_snapshot": input_fingerprint(template.to_dict()), "part_ref": template.part_ref,
            "part_no": template.part_no, "part_name": template.part_name, "sequence": template.sequence,
            "operation_label": template.operation_label, "source": template.source,
            "old_unit_hours": template.old_unit_hours, **summary,
            "status": "suggested" if suggested is not None else "insufficient_data",
            **_deviation(old, suggested),
            "method_version": METHOD_VERSION, "generated_at": generated_at,
            "capabilities": closed_capabilities(), "blocked_reasons": reasons,
            "write_context": {"write_token": None, "expires_at": None, "capabilities": [], "blocked_reasons": reasons}}

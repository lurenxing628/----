"""Re-read canonical calibration facts; never accept client-supplied statistics."""

from datetime import datetime
from typing import Callable

from core.models.workbench_calibration import MAX_SAMPLES, MIN_SAMPLES, CalibrationQuery, issue
from core.models.workbench_calibration_adoption import MAX_EVIDENCE_BYTES, CalibrationAdoptionEvidence
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_template_lineage import snapshot

from .calibration_facts import CalibrationFacts
from .calibration_samples import number


def read_evidence(conn, repo, template_ref, intent, clock: Callable[[], datetime]):
    if not conn.in_transaction:
        raise RuntimeError("Calibration evidence requires a caller-owned SQLite snapshot.")
    repo.require_schema()
    as_of = clock()
    facts_reader = CalibrationFacts(conn, as_of=as_of)
    with facts_reader.read_snapshot():
        template = repo.template(template_ref)
        facts = facts_reader.read(CalibrationQuery(part_ref=template["part_ref"]))
        row = next((row for row in facts["rows"] if row["template_operation_ref"] == template_ref), None)
        if row is None:
            raise WorkbenchCommandRejected("entity_not_found", "当前模板建议已不可用，不能改指同号模板。", 404)
        locks = repo.read_locks([template_ref])
        suggestion = {key: value for key, value in row.items() if key not in
                      ("generated_at", "capabilities", "blocked_reasons", "write_context")}
        selected = {sample["sample_ref"]: sample for sample in facts["samples_by_template"].get(template_ref, []) if sample["selected"]}
        samples = [selected[ref] for ref in suggestion["sample_refs"]]
        preview_intent = {key: intent[key] for key in ("reason", "declared_operator")}
        binding = {"source": "production", "intent": preview_intent, "template": snapshot(template),
                   "facts_fingerprint": facts["fingerprint"], "suggestion": suggestion, "locks": locks}
        blockers = _blockers(template, suggestion, samples, facts["lineage_available"], locks)
        evidence = CalibrationAdoptionEvidence(template, suggestion, samples, binding, as_of.isoformat(timespec="seconds"), blockers)
        encoded = canonical_json({"snapshot": binding, "suggestion": suggestion, "samples": samples})
        if len(encoded.encode("utf-8")) > MAX_EVIDENCE_BYTES:
            raise WorkbenchCommandRejected("query_too_large", "完整采纳证据超过8MB，未截断样本，请缩小范围后重试。", 413)
        return evidence


def _blockers(template, suggestion, samples, lineage_available, locks):
    blockers = []
    if locks:
        blockers.append(issue("calibration_quota_locked", "此模板定额已采纳并锁定，不能重复采纳或覆盖。"))
    if not lineage_available:
        blockers.append(issue("template_lineage_missing", "缺少已核实的模板复制来源，不能采纳。"))
    if template["source"] != "internal":
        blockers.append(issue("processing_basis_unconfirmed", "只有已确认自制加工口径的模板才能采纳。"))
    value = number(suggestion["suggested_unit_hours"])
    if value is None or not MIN_SAMPLES <= suggestion["sample_count"] <= MAX_SAMPLES:
        blockers.append(issue("insufficient_samples", "当前模板修订的合格整道完工样本不足5个，不能采纳。"))
    if len(samples) != suggestion["sample_count"] or any(not row["eligible"] for row in samples):
        raise WorkbenchCommandRejected("calibration_source_unavailable", "所选样本与统计证据不一致，未执行采纳。", 500)
    return blockers

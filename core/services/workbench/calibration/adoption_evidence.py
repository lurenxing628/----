"""Re-read canonical calibration facts; never accept client-supplied statistics."""

from datetime import datetime
from typing import Callable

from core.models.workbench_calibration import (
    MAX_SAMPLES,
    MIN_SAMPLES,
    SUGGESTION_BELOW_PRECISION_CODE,
    issue,
)
from core.models.workbench_calibration_adoption import MAX_EVIDENCE_BYTES, CalibrationAdoptionEvidence
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_template_lineage import snapshot

from .adoption_policy import require_template
from .facts import CalibrationFacts
from .samples import ensure_sample_reports, ensure_sample_revision


def _source_revisions(detail):
    samples = [
        ensure_sample_revision(sample)
        for sample in detail["linked_samples"] + detail["unbound_samples"]
    ]
    return [
        {key: sample[key] for key in ("sample_ref", "sample_revision", "eligible", "exclusion_reasons")}
        for sample in sorted(samples, key=lambda row: row["sample_ref"])
    ]


def read_evidence(conn, repo, template_ref, intent, clock: Callable[[], datetime]):
    if not conn.in_transaction:
        raise RuntimeError("Calibration evidence requires a caller-owned SQLite snapshot.")
    as_of = clock()
    facts_reader = CalibrationFacts(conn)
    with facts_reader.read_snapshot() as ledger_scope:
        template, cal_template = require_template(repo, template_ref)
        detail = facts_reader.read_single_template(ledger_scope, cal_template, as_of=as_of)
        row = detail["row"]
        latest = repo.latest_adoption(template_ref)
        suggestion = {
            key: value
            for key, value in row.items()
            if key not in ("generated_at", "capabilities", "blocked_reasons", "write_context")
        }
        selected = {
            sample["sample_ref"]: sample
            for sample in detail["linked_samples"]
            if sample["selected"]
        }
        samples = [
            ensure_sample_reports(selected[ref], report_histories=detail["report_histories"])
            for ref in suggestion["sample_refs"]
        ]
        preview_intent = {key: intent[key] for key in ("reason", "declared_operator")}
        binding = {
            "schema_version": 2,
            "source": "production",
            "intent": preview_intent,
            "template": snapshot(template),
            "source_revisions": _source_revisions(detail),
            "lineage_available": detail["lineage_available"],
            "source_constraints": detail["source_constraints"],
            "suggestion": suggestion,
            "latest_adoption": latest,
        }
        method_blockers = [
            reason
            for reason in row["blocked_reasons"]
            if reason["code"] == SUGGESTION_BELOW_PRECISION_CODE
        ]
        blockers = _blockers(template, suggestion, method_blockers)
        evidence = CalibrationAdoptionEvidence(
            template,
            suggestion,
            samples,
            binding,
            as_of.isoformat(timespec="seconds"),
            blockers,
        )
        encoded = evidence.audit_document()
        if len(encoded.encode("utf-8")) > MAX_EVIDENCE_BYTES:
            raise WorkbenchCommandRejected("query_too_large", "采用依据超过 8 MB，系统没有截断完工记录，请缩小范围后重试。", 413)
        return evidence


def _blockers(template, suggestion, method_blockers):
    blockers = []
    if template["source"] != "internal":
        blockers.append(issue("processing_basis_unconfirmed", "只有已确认按自制加工计算的模板才能采用。"))
    if suggestion["suggested_unit_hours"] is None or not MIN_SAMPLES <= suggestion["sample_count"] <= MAX_SAMPLES:
        blockers.append(issue("insufficient_samples", "这个模板版本下合格的整道完工记录不足 5 条，不能采用。"))
    blockers.extend(method_blockers)
    return blockers

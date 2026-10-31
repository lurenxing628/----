"""Adoption reuses its canonical evidence and current template transaction facts."""

from collections import Counter

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models import workbench_calibration_adoption as evidence_model
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.calibration import adoption_evidence
from core.services.workbench.calibration.adoption_policy import adopt_checked_quota
from data.repositories.workbench_calibration_adoption_repo import WorkbenchCalibrationAdoptionRepository
from tests.workbench.calibration_adoption_support import INTENT, KEY, PREVIEW_INTENT, service, token
from tests.workbench.calibration_adoption_support import adoption_case as _adoption_case  # noqa: F401
from tests.workbench.calibration_adoption_support import ready_adoption_case as _ready_case  # noqa: F401
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage_case  # noqa: F401


def test_confirmation_reads_template_and_encodes_audit_once(ready_adoption_case, monkeypatch):
    case = ready_adoption_case
    write_token = token(case)
    calls = Counter()
    original_template = WorkbenchCalibrationAdoptionRepository.template
    original_encode = evidence_model.canonical_json

    def template(repo, ref):
        calls["template"] += 1
        return original_template(repo, ref)

    def encode(value):
        calls["encode"] += 1
        return original_encode(value)

    monkeypatch.setattr(WorkbenchCalibrationAdoptionRepository, "template", template)
    monkeypatch.setattr(evidence_model, "canonical_json", encode)
    result = service(case.conn).confirm(case.template_ref, write_token, KEY, INTENT)
    assert calls == {"template": 1, "encode": 1}
    actual = original_template(service(case.conn).repo, case.template_ref)
    assert actual is not None
    assert actual["unit_hours"] == result["data"]["new_unit_hours"] == 3.0
    assert type(actual["unit_hours"]) is type(result["data"]["new_unit_hours"]) is float
    assert actual["template_revision"] == result["data"]["template_revision_after"]


def test_same_quota_keeps_template_revision_and_all_current_facts(ready_adoption_case):
    case = ready_adoption_case
    repo = WorkbenchCalibrationAdoptionRepository(case.conn)
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        template = repo.template(case.template_ref)
        assert template is not None
        before = case.conn.total_changes
        after = adopt_checked_quota(repo, template, template["unit_hours"])
        assert after == template
        assert case.conn.total_changes == before
        stored = repo.template(case.template_ref)
        assert stored is not None
        assert stored == after


def test_evidence_limit_still_uses_the_complete_utf8_document(ready_adoption_case, monkeypatch):
    case = ready_adoption_case
    intent = {**PREVIEW_INTENT, "reason": "核对完工记录后采用"}
    with TransactionManager(case.conn).transaction():
        evidence = adoption_evidence.read_evidence(case.conn, service(case.conn).repo,
                                                 case.template_ref, intent, service(case.conn).clock)
    document = evidence.audit_document()
    byte_size = len(document.encode("utf-8"))
    assert byte_size > len(document)
    monkeypatch.setattr(adoption_evidence, "MAX_EVIDENCE_BYTES", len(document))
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        service(case.conn).preview(case.template_ref, intent)
    assert rejected.value.code == "query_too_large" and rejected.value.status == 413
    monkeypatch.setattr(adoption_evidence, "MAX_EVIDENCE_BYTES", byte_size)
    assert service(case.conn).preview(case.template_ref, intent)["validation"]["can_adopt"]


def test_calibration_reads_report_heads_and_complete_history_together(ready_adoption_case):
    case = ready_adoption_case
    original = case.report_projection(case.reports[0]["report_ref"])
    case.command("correct", original.report_ref,
                 {"remark": "Checked the complete history", "original_revision_ref": original.revision_ref,
                  "reason": "Verified the production record", "declared_operator": "Reviewer"})
    statements = []
    case.conn.set_trace_callback(statements.append)
    try:
        preview = service(case.conn).preview(case.template_ref, PREVIEW_INTENT)
    finally:
        case.conn.set_trace_callback(None)
    reads = [sql for sql in statements if "FROM WorkbenchProductionReports" in sql]
    assert len(reads) == 1
    assert "LEFT JOIN WorkbenchProductionReportRevisions" in reads[0]
    sample = next(row for row in preview["samples"] if original.report_ref in row["report_refs"])
    assert len(sample["reports"][0]["correction_history"]) == 2
    assert preview["validation"]["can_adopt"]


def test_calibration_checks_stored_orphan_report_heads_and_read_limit(ready_adoption_case, monkeypatch):
    from core.services.execution import ledger_reader

    case = ready_adoption_case
    monkeypatch.setattr(ledger_reader, "MAX_FACT_ROWS", len(case.reports) - 1)
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        service(case.conn).preview(case.template_ref, PREVIEW_INTENT)
    assert rejected.value.code == "query_too_large" and rejected.value.status == 413


def test_calibration_prebinds_snapshot_once_per_part_and_defers_report_dto_until_detail(ready_adoption_case, monkeypatch):
    from core.models.workbench_calibration import CalibrationQuery
    from core.models.workbench_execution import ProductionReport
    from core.services.workbench.calibration.service import WorkbenchCalibrationService
    from data.repositories.workbench_calibration_query_repo import WorkbenchCalibrationQueryRepository
    from tests.workbench.execution_ledger_support import NOW

    case = ready_adoption_case
    part_ref = case.conn.execute(
        "SELECT ref FROM WorkbenchEntityRefs WHERE kind='part' AND entity_key='P1' AND active=1"
    ).fetchone()[0]
    calls = Counter()
    orig_part_identity = WorkbenchCalibrationQueryRepository.part_identity
    orig_template_rows = WorkbenchCalibrationQueryRepository.template_rows
    orig_report_to_dict = ProductionReport.to_dict

    monkeypatch.setattr(
        WorkbenchCalibrationQueryRepository,
        "part_identity",
        lambda repo, ref: (calls.__setitem__("part_identity", calls["part_identity"] + 1), orig_part_identity(repo, ref))[1],
    )
    monkeypatch.setattr(
        WorkbenchCalibrationQueryRepository,
        "template_rows",
        lambda repo, part_no, limit: (calls.__setitem__("template_rows", calls["template_rows"] + 1), orig_template_rows(repo, part_no, limit))[1],
    )
    monkeypatch.setattr(
        ProductionReport,
        "to_dict",
        lambda self: (calls.__setitem__("report_to_dict", calls["report_to_dict"] + 1), orig_report_to_dict(self))[1],
    )

    cal = WorkbenchCalibrationService(case.conn, as_of=NOW)
    with pytest.raises(WorkbenchCommandRejected) as stale:
        cal.read(
            CalibrationQuery(part_ref=part_ref),
            bind_snapshot=lambda _content: (_ for _ in ()).throw(
                WorkbenchCommandRejected("snapshot_stale", "stale", 409)
            ),
        )
    assert stale.value.code == "snapshot_stale"
    assert calls["part_identity"] == 1 and calls["template_rows"] == 0

    calls.clear()
    from core.services.execution import projection as exec_projection

    orig_build_history = exec_projection.build_correction_history
    monkeypatch.setattr(
        exec_projection,
        "build_correction_history",
        lambda *a, **kw: (calls.__setitem__("correction_history", calls["correction_history"] + 1), orig_build_history(*a, **kw))[1],
    )
    facts = cal.read(
        CalibrationQuery(part_ref=part_ref),
        bind_snapshot=lambda _content: {"snapshot_ref": "snap-1", "as_of": NOW.isoformat(timespec="seconds")},
    )
    assert calls["part_identity"] == 1 and calls["template_rows"] == 1
    assert calls["report_to_dict"] == 0 and calls["correction_history"] == 0
    list_data, _ = cal.workspace(facts, CalibrationQuery(part_ref=part_ref), facts["snapshot"], suggestion_ref=None, export=False)
    assert calls["report_to_dict"] == 0 and calls["correction_history"] == 0 and len(list_data["items"]) == 1
    detail_data, _ = cal.workspace(
        facts, CalibrationQuery(part_ref=part_ref), facts["snapshot"], suggestion_ref=case.template_ref, export=False
    )
    assert calls["report_to_dict"] == sum(len(sample["reports"]) for sample in detail_data["samples"]) > 0
    assert calls["correction_history"] == calls["report_to_dict"]
    assert all(isinstance(sample["reports"][0], dict) for sample in detail_data["samples"] if sample["reports"])
    assert all(len(report["correction_history"]) >= 1 for sample in detail_data["samples"] for report in sample["reports"])

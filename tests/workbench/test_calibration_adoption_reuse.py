"""Adoption reuses its canonical evidence and current template transaction facts."""

from collections import Counter

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models import workbench_calibration_adoption as evidence_model
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.template_hours import ProcessTemplateHours
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
    original_current = ProcessTemplateHours.current
    original_encode = evidence_model.canonical_json

    def template(repo, ref):
        calls["template"] += 1
        return original_template(repo, ref)

    def current(writer, refs):
        calls["current"] += 1
        return original_current(writer, refs)

    def encode(value):
        calls["encode"] += 1
        return original_encode(value)

    monkeypatch.setattr(WorkbenchCalibrationAdoptionRepository, "template", template)
    monkeypatch.setattr(ProcessTemplateHours, "current", current)
    monkeypatch.setattr(evidence_model, "canonical_json", encode)
    result = service(case.conn).confirm(case.template_ref, write_token, KEY, INTENT)
    assert calls == {"template": 1, "encode": 1}
    actual = original_template(service(case.conn).repo, case.template_ref)
    assert actual["unit_hours"] == result["data"]["new_unit_hours"] == 3.0
    assert type(actual["unit_hours"]) is type(result["data"]["new_unit_hours"]) is float
    assert actual["template_revision"] == result["data"]["template_revision_after"]


def test_same_quota_keeps_template_revision_and_all_current_facts(ready_adoption_case):
    case = ready_adoption_case
    repo = WorkbenchCalibrationAdoptionRepository(case.conn)
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        template = repo.template(case.template_ref)
        before = case.conn.total_changes
        after = adopt_checked_quota(repo, template, template["unit_hours"])
        assert after == template
        assert case.conn.total_changes == before
        assert repo.template(case.template_ref) == after


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

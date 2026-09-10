"""Transport uses shared write contexts/receipts; browser input cannot choose facts."""

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_calibration_adoption import ADOPT_ACTION
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.calibration_adoption_evidence import read_evidence
from data.repositories.workbench_calibration_adoption_repo import WorkbenchCalibrationAdoptionRepository
from tests.workbench.calibration_adoption_support import (
    BASE,
    INTENT,
    KEY,
    PREVIEW_INTENT,
    assert_rejected,
    service,
    snapshot,
    token,
)
from tests.workbench.calibration_adoption_support import adoption_case as _adoption_case  # noqa: F401
from tests.workbench.calibration_adoption_support import ready_adoption_case as _ready_case  # noqa: F401
from tests.workbench.test_execution_ledger_support import NOW
from tests.workbench.test_template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.test_template_lineage_support import lineage_case as _lineage_case  # noqa: F401
from web.routes.workbench.write_context import issue_write_context


def test_http_preview_confirm_and_scoped_receipt(ready_adoption_case):
    case = ready_adoption_case
    base = BASE + case.template_ref
    response = case.client.post(base + "/adopt-preview", json={"input": PREVIEW_INTENT})
    assert response.status_code == 200
    preview = response.get_json()["data"]
    assert response.headers["Cache-Control"] == "no-store"
    payload = {"input": INTENT, "write_token": preview["write_context"]["write_token"], "request_key": KEY}
    result = case.client.post(base + "/adopt", json=payload)
    assert result.status_code == 200 and result.get_json()["result"] == "committed"
    replay = case.client.post(base + "/adopt", json={**payload, "write_token": "expired"})
    receipt = case.client.get(base + "/adopt/receipts/" + KEY)
    assert receipt.get_json() == replay.get_json()
    assert replay.get_json()["replayed"] is True
    assert_rejected(case.client.get(BASE + "a" * 48 + "/adopt/receipts/" + KEY), "request_key_conflict", 409)
    assert_rejected(case.client.get(base + "/adopt/receipts/" + KEY + "-missing"), "receipt_not_found", 404)


@pytest.mark.parametrize("extra", [{"suggested_unit_hours": 999}, {"sample_refs": ["a" * 48]}, {"application_operator": "browser"}, {"source": "production"}])
def test_client_cannot_supply_values_samples_or_operator(ready_adoption_case, extra):
    case = ready_adoption_case
    before = snapshot(case.conn)
    response = case.client.post(BASE + case.template_ref + "/adopt-preview", json={"input": {**PREVIEW_INTENT, **extra}})
    assert_rejected(response, "invalid_input", 400)
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("reason", [None, "", "  ", 10, True, "\x00", "x" * 2001])
def test_reason_is_required_before_any_write(adoption_case, reason):
    case = adoption_case
    before = snapshot(case.conn)
    response = case.client.post(BASE + case.template_ref + "/adopt-preview", json={"input": {**PREVIEW_INTENT, "reason": reason}})
    assert_rejected(response, "invalid_input", 422)
    assert snapshot(case.conn) == before


def test_disabled_and_unusable_or_expired_token_never_write(ready_adoption_case, monkeypatch):
    case = ready_adoption_case
    write_token = token(case)
    before = snapshot(case.conn)
    base = BASE + case.template_ref
    case.app.config["WORKBENCH_CALIBRATION_ADOPTION_ENABLED"] = False
    assert_rejected(case.client.post(base + "/adopt-preview", json={"input": PREVIEW_INTENT}), "calibration_adoption_not_connected", 503)
    case.app.config["WORKBENCH_CALIBRATION_ADOPTION_ENABLED"] = True
    for value in (None, "", "unknown", 12):
        response = case.client.post(base + "/adopt", json={"write_token": value, "request_key": KEY, "input": INTENT})
        assert_rejected(response, "stale_write", 409)
    monkeypatch.setattr("web.public_token_registry.time.time", lambda: 10**12)
    response = case.client.post(base + "/adopt", json={"write_token": write_token, "request_key": KEY, "input": INTENT})
    assert_rejected(response, "stale_write", 409)
    assert snapshot(case.conn) == before


def test_database_guard_rejects_insufficient_samples_even_with_internal_token(adoption_case):
    case = adoption_case
    repo = WorkbenchCalibrationAdoptionRepository(case.conn)
    with TransactionManager(case.conn).transaction():
        evidence = read_evidence(case.conn, repo, case.template_ref, INTENT, lambda: NOW)
        context = issue_write_context(case.template_ref, [ADOPT_ACTION], evidence.snapshot)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).confirm(case.template_ref, context["write_token"], KEY, INTENT)
    assert error.value.code == "insufficient_samples"


def test_storage_failure_is_unknown_not_success_and_receipt_is_queryable(ready_adoption_case):
    case = ready_adoption_case
    write_token = token(case)
    case.conn.execute("CREATE TRIGGER co_fail_http BEFORE INSERT ON WorkbenchCalibrationQuotaLocks BEGIN SELECT RAISE(ABORT,'CO fail'); END")
    response = case.client.post(BASE + case.template_ref + "/adopt", json={"write_token": write_token, "request_key": KEY, "input": INTENT})
    assert response.status_code == 500
    assert response.get_json()["committed"] == "unknown"
    assert response.get_json()["error"]["request_key"] == KEY
    assert_rejected(case.client.get(BASE + case.template_ref + "/adopt/receipts/" + KEY), "receipt_not_found", 404)


@pytest.mark.parametrize("declared_operator", [None, "", "  ", 10, True, "\x00", "x" * 101])
def test_declared_operator_required_and_validated_independently(adoption_case, declared_operator):
    case = adoption_case
    before = snapshot(case.conn)
    response = case.client.post(BASE + case.template_ref + "/adopt-preview",
        json={"input": {**PREVIEW_INTENT, "declared_operator": declared_operator}})
    assert_rejected(response, "invalid_input", 422)
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("confirm", [False, None, 1, 0, "true", {}])
def test_confirm_requires_explicit_true_not_truthy_values(ready_adoption_case, confirm):
    case = ready_adoption_case
    write_token = token(case)
    before = snapshot(case.conn)
    response = case.client.post(BASE + case.template_ref + "/adopt",
        json={"input": {**INTENT, "confirm": confirm}, "write_token": write_token, "request_key": KEY})
    assert_rejected(response, "confirmation_required", 422)
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("intent", [{"reason": "old reason-only DTO"}, PREVIEW_INTENT, {**PREVIEW_INTENT, "confirmed": True}])
def test_confirm_does_not_silently_accept_old_or_missing_confirmation_dto(ready_adoption_case, intent):
    case = ready_adoption_case
    before = snapshot(case.conn)
    response = case.client.post(BASE + case.template_ref + "/adopt",
        json={"input": intent, "write_token": token(case), "request_key": KEY})
    assert_rejected(response, "invalid_input", 400)
    assert snapshot(case.conn) == before


def test_declared_operator_is_preview_bound_and_preserved_in_receipt(ready_adoption_case):
    case = ready_adoption_case
    write_token = token(case)
    base = BASE + case.template_ref
    changed = {**INTENT, "declared_operator": "Changed reviewer"}
    payload = {"input": changed, "write_token": write_token, "request_key": KEY}
    assert_rejected(case.client.post(base + "/adopt", json=payload), "stale_write", 409)
    saved = case.client.post(base + "/adopt", json={**payload, "input": INTENT})
    assert saved.status_code == 200
    data = saved.get_json()["data"]
    assert data["declared_operator"] == INTENT["declared_operator"] != data["application_operator"]
    assert data["confirmed"] is True
    assert_rejected(case.client.post(base + "/adopt", json=payload), "request_key_conflict", 409)
    receipt = case.client.get(base + "/adopt/receipts/" + KEY).get_json()["data"]
    assert receipt == data

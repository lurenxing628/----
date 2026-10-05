"""Repeated equipment authorizations do not skip per-operation work qualifications."""

from types import SimpleNamespace

import pytest

from core.services.personnel.operator_qualification import (
    OperatorQualificationError,
    OperatorQualificationService,
    validate_fixed_operator_qualifications,
)
from data.repositories.operator_machine_repo import OperatorMachineRepository


def test_fixed_authorization_is_read_once_but_every_work_type_is_checked(monkeypatch):
    calls = []
    monkeypatch.setattr(OperatorQualificationService, "load", lambda self, ids: {"O1": {"cut"}})
    monkeypatch.setattr(OperatorMachineRepository, "exists", lambda self, oid, mid: calls.append((oid, mid)) or True)
    operations = [SimpleNamespace(source="internal", operator_id="O1", machine_id="M1", op_type_id=kind)
                  for kind in ("cut", "cut", "turn")]
    with pytest.raises(OperatorQualificationError) as error:
        validate_fixed_operator_qualifications(object(), operations)
    assert error.value.details["reason"] == "operator_skill_not_qualified"
    assert calls == [("O1", "M1")]


def test_fixed_authorization_checks_each_distinct_pair(monkeypatch):
    calls = []
    monkeypatch.setattr(OperatorQualificationService, "load", lambda self, ids: {"O1": {"cut"}})
    monkeypatch.setattr(OperatorMachineRepository, "exists", lambda self, oid, mid: calls.append((oid, mid)) or mid == "M1")
    operations = [SimpleNamespace(source="internal", operator_id="O1", machine_id=machine, op_type_id="cut")
                  for machine in ("M1", "M1", "M2")]
    with pytest.raises(OperatorQualificationError) as error:
        validate_fixed_operator_qualifications(object(), operations)
    assert error.value.details["reason"] == "operator_machine_not_authorized"
    assert calls == [("O1", "M1"), ("O1", "M2")]

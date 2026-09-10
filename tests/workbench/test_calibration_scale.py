"""Cardinality bounds, one projection, and complete-result byte guards."""

import time

import pytest

from core.services.workbench.execution_ledger import ExecutionLedgerService
from tests.workbench.test_calibration_support import BASE, assert_failure, ledger_fixture, scope_token
from tests.workbench.test_calibration_support import calibration_api as api_fixture
from tests.workbench.test_calibration_support import calibration_case as case_fixture


def add_templates(case, count):
    case.conn.executemany("INSERT INTO PartOperations(part_no,seq,op_type_name,unit_hours) VALUES ('P1',?,'Scale',1)",
                         ((index + 2,) for index in range(count)))


def add_instances(case, count):
    case.conn.executemany("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source) VALUES (?,'B1',?,'Scale','internal')",
                         (("SCALE-" + str(index), index + 2) for index in range(count)))


def test_many_templates_share_one_projection_without_cartesian_samples(calibration_api, monkeypatch):
    case = calibration_api
    add_templates(case, 999)
    add_instances(case, 1999)
    case.conn.commit()
    calls = []
    original = ExecutionLedgerService.project_loaded

    def counted(self, facts, **kwargs):
        calls.append(len(facts["operations"]))
        return original(self, facts, **kwargs)

    monkeypatch.setattr(ExecutionLedgerService, "project_loaded", counted)
    statements = []
    case.conn.set_trace_callback(statements.append)
    start = time.monotonic()
    data = scope_token(case)["data"]
    elapsed = time.monotonic() - start
    assert data["page"]["total"] == 1000 and len(data["items"]) == 20
    assert calls == [2000]
    assert all(row["candidate_count"] == 2000 and row["sample_count"] == 0 for row in data["items"])
    assert len(statements) < 150
    print(f"calibration scale: templates=1000 instances=2000 sql={len(statements)} seconds={elapsed:.3f}")


@pytest.mark.parametrize("count", [10000, 10001])
def test_template_capacity_rejects_instead_of_truncates(calibration_api, count):
    case = calibration_api
    add_templates(case, count - 1)
    case.conn.commit()
    response = case.client.get(BASE)
    if count == 10000:
        assert response.status_code == 200 and response.get_json()["data"]["page"]["total"] == count
    else:
        assert_failure(response, "query_too_large", 413)


@pytest.mark.parametrize("count", [10000, 10001])
def test_instance_capacity_rejects_instead_of_truncates(calibration_api, count):
    case = calibration_api
    add_instances(case, count - 1)
    case.conn.commit()
    response = case.client.get(BASE)
    if count == 10000:
        assert response.status_code == 200 and response.get_json()["data"]["items"][0]["candidate_count"] == count
    else:
        assert_failure(response, "query_too_large", 413)


def test_json_export_and_xlsx_cell_limits(calibration_api, monkeypatch):
    case = calibration_api
    payload = scope_token(case)
    token = payload["meta"]["snapshot_ref"]
    monkeypatch.setattr("web.routes.workbench.calibration.MAX_RESPONSE_BYTES", 10)
    assert_failure(case.client.get(BASE), "query_too_large", 413)
    monkeypatch.setattr("core.services.workbench.calibration_export.MAX_EXPORT_BYTES", 10)
    assert_failure(case.client.get(BASE + "/export", query_string={"snapshot_ref": token}), "export_too_large", 413)


def test_xlsx_does_not_silently_truncate_long_original_text(calibration_api):
    case = calibration_api
    case.conn.execute("UPDATE Parts SET part_name=?", ("x" * 32768,))
    case.conn.commit()
    token = scope_token(case)["meta"]["snapshot_ref"]
    assert_failure(case.client.get(BASE + "/export", query_string={"snapshot_ref": token, "format": "xlsx"}), "export_too_large", 413)
    response = case.client.get(BASE + "/export", query_string={"snapshot_ref": token, "format": "csv"})
    assert response.status_code == 200 and ("x" * 32768).encode() in response.data

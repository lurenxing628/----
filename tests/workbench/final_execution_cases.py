"""Named fixtures and payload builders; every request goes to the owned factory host."""

import json
import os
import uuid
from contextlib import closing
from pathlib import Path

import pytest

from core.infrastructure.database import get_connection
from tests.workbench.final_execution_support import build, serving

EXECUTION = "/api/workbench/v1/execution"
CALIBRATION = "/api/workbench/v1/calibration"
CREATE_TABLES = {"WorkbenchProductionReports", "WorkbenchProductionReportRevisions",
                 "WorkbenchCommandReceipts", "WorkbenchExecutionLedgerClock"}
CORRECT_TABLES = CREATE_TABLES - {"WorkbenchProductionReports"}
ADOPT_TABLES = {"PartOperations", "WorkbenchEntityRefs", "WorkbenchCalibrationAdoptions",
                "WorkbenchCalibrationQuotaLocks", "WorkbenchCommandReceipts"}


@pytest.fixture(scope="session")
def final_e_runtime(tmp_path_factory):
    parent = Path(os.environ["FINAL_E_PARENT"]).resolve() if os.environ.get("FINAL_E_PARENT") else tmp_path_factory.mktemp("final-execution")
    built, runtime = build(parent)
    return parent, built, runtime


@pytest.fixture
def final_execution_host(final_e_runtime):
    parent, built, runtime = final_e_runtime
    with serving(parent, built, runtime, "execution") as host:
        print("FINAL_EXECUTION_ROOT " + str(host.root), flush=True)
        yield host


@pytest.fixture
def final_calibration_host(final_e_runtime):
    parent, built, runtime = final_e_runtime
    with serving(parent, built, runtime, "calibration") as host:
        print("FINAL_CALIBRATION_ROOT " + str(host.root), flush=True)
        yield host


def seed(host):
    return host.ready["expected"]["final_e"]


def task(host, op=1):
    ref = seed(host)["task_refs"][str(op)]
    return host.json(EXECUTION + "/tasks/" + ref)["data"]["task"]


def values(host, quantity=2, **patch):
    return {"actual_start": "2026-09-02T08:00:00", "actual_end": "2026-09-02T10:00:00",
            "completed_quantity": quantity, "effective_processing_hours": 1.5,
            "actual_machine_ref": seed(host)["machine_ref"], "actual_operator_ref": seed(host)["operator_ref"],
            "remark": "本轮真实完整主入口报工", **patch}


def command(context, data, key=None):
    return {"request_key": key or "final-e-" + uuid.uuid4().hex, "write_token": context["write_token"], "input": data}


def create(host, data=None, op=1, status=200):
    current = task(host, op)
    body = command(current["execution"]["write_context"], values(host) if data is None else data)
    result = host.json(EXECUTION + "/tasks/" + current["task_ref"] + "/reports", body=body, status=status)
    return body, result


def revise(host, report, data, action="correct", status=200):
    current = task(host)
    record = next(row for row in current["execution"]["reports"] if row["report_ref"] == report["report_ref"])
    body = command(record["write_context"], {"original_revision_ref": record["revision_ref"], "reason": "逐项核对后的更正", **data})
    result = host.json(EXECUTION + "/reports/" + record["report_ref"] + "/" + action, body=body, status=status)
    return body, result


def sql(host, statement, parameters=()):
    with closing(get_connection(str(host.root / "db/aps-live.db"))) as conn:
        with conn:
            result = [dict(row) for row in conn.execute(statement, parameters)]
    return result


def preview_file(host, content, reading=None):
    reading = reading or host.json(EXECUTION + "/tasks")
    boundary = "final-e-" + uuid.uuid4().hex
    fields = {"scope": json.dumps(reading["data"]["scope"]), "snapshot_ref": reading["meta"]["snapshot_ref"]}
    parts = []
    for name, value in fields.items():
        parts.append(("--" + boundary + '\r\nContent-Disposition: form-data; name="' + name + '"\r\n\r\n' + value + "\r\n").encode())
    parts.extend([("--" + boundary + '\r\nContent-Disposition: form-data; name="file"; filename="final-e.xlsx"\r\n'
                  "Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n").encode(),
                  content, ("\r\n--" + boundary + "--\r\n").encode()])
    status, _, raw = host.request(EXECUTION + "/files/preview", raw=b"".join(parts),
                                  headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    payload = json.loads(raw.decode())
    assert status == 200, payload
    return payload


def confirm_file(host, preview, *, status=200):
    data = preview["data"]
    body = command(data["write_context"], {"preview_ref": data["preview_ref"]})
    return body, host.json(EXECUTION + "/files/confirm", body=body, status=status)

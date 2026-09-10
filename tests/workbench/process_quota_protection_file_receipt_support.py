"""CW receipt-only HTTP fixtures, with actual routes and per-request connections."""

import json
import uuid
from datetime import datetime, timedelta
from io import BytesIO

import pytest
from flask import Blueprint, g

from core.services.workbench.process_file_codec import encode_process_file
from tests.workbench.calibration_adoption_support import INTENT, KEY, service, token
from tests.workbench.process_quota_protection_support import adopt, connect
from web.routes.workbench.materials import command_receipt
from web.routes.workbench.process_files import register_process_file_routes

BASE = "/api/workbench/v1"


def success(response):
    body = response.get_json()
    assert response.status_code == 200 and body["ok"] is True, body
    return body


@pytest.fixture(name="quota_file_api")
def quota_file_api(quota_case):
    case = quota_case
    bp = Blueprint("workbench", __name__)
    register_process_file_routes(bp)
    bp.add_url_rule(BASE + "/commands/<request_key>", view_func=command_receipt, methods=["GET"])
    case.app.register_blueprint(bp)

    @case.app.before_request
    def database():
        g.db = connect(case)

    @case.app.teardown_request
    def close_database(_error):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    return QuotaFileAPI(case)


@pytest.fixture(name="locked_quota_file_api")
def locked_quota_file_api(quota_file_api):
    adopt(quota_file_api.case)
    return quota_file_api


class QuotaFileAPI:
    def __init__(self, case):
        self.case = case
        self.client = case.app.test_client()

    def preview(self, rows, *, fmt="csv", target=None, kind="hours"):
        content = encode_process_file(kind, rows, fmt).content
        data = {"file": (BytesIO(content), "input." + fmt), "format": fmt, "mode": "upsert"}
        if target is not None:
            data["target_ref"] = target
        return success(self.client.post(BASE + "/process-files/" + kind + "/preview", data=data))

    @staticmethod
    def body(preview, *, key=None):
        data = preview["data"]
        return {"request_key": key or "cw-file-receipt-" + uuid.uuid4().hex,
                "write_token": data["write_context"]["write_token"],
                "input": {"preview_ref": data["preview_ref"], "discard_group_refs": [], "confirm_zero_unit_hours": False}}

    def confirm(self, body, *, kind="hours"):
        return self.client.post(BASE + "/process-files/" + kind + "/confirm", json=body)

    def receipt(self, key):
        return success(self.client.get(BASE + "/commands/" + key))

    def stored_outcome(self, key):
        conn = connect(self.case)
        try:
            row = conn.execute("SELECT outcome_json FROM WorkbenchCommandReceipts WHERE request_key=?", (key,)).fetchone()
            assert row is not None
            return json.loads(row[0])
        finally:
            conn.close()


def file_rows(*rows):
    return [{"business_code": "P1", **row} for row in rows]


def assert_tables_preserved(before, after, allowed=("WorkbenchCommandReceipts",)):
    assert set(before) == set(after)
    for table, rows in before.items():
        if table not in allowed:
            assert after[table] == rows, table


def adopt_second(case):
    ids = [case.conn.execute("""SELECT second.id FROM BatchOperations first JOIN BatchOperations second
        ON second.batch_id=first.batch_id AND second.seq=2 WHERE first.id=?""", (key,)).fetchone()[0] for key in case.ids]
    case.plan(3, ids)
    for index, (op_id, value) in enumerate(zip(ids, [4, 5, 6, 7, 8])):
        end = datetime(2026, 9, 9, 10) + timedelta(minutes=index)
        start = end - timedelta(hours=value * 10 + 1)
        case.command("create", case.task(3, op_id), case.values(10, effective_processing_hours=value * 10,
            actual_start=start.isoformat(), actual_end=end.isoformat()))
    intent = {**INTENT, "reason": "CW second verified quota"}
    preview_input = {key: value for key, value in intent.items() if key != "confirm"}
    return service(case.conn).confirm(case.other_ref, token(case, ref=case.other_ref, intent=preview_input), KEY + "-second", intent)

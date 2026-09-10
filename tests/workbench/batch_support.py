"""Isolated SQLite and registered functions; never import the production app."""

import pytest
from flask import Blueprint, Flask, g

from tests.workbench.identity_metadata_support import insert_row, seed_resources
from tests.workbench.process_workflow_support import stored_state

BASE = "/api/workbench/v1/entities/batch"


@pytest.fixture(name="batch_client")
def batch_database(schema_conn):
    return create_batch_client(schema_conn)


def create_batch_client(schema_conn):
    from web.routes.workbench.batches import register_batch_routes
    from web.routes.workbench.materials import command_receipt

    seed_resources(schema_conn, relations=True)
    schema_conn.execute("UPDATE Machines SET status='active' WHERE machine_id='M1'")
    schema_conn.execute("UPDATE Suppliers SET status='active' WHERE supplier_id='S1'")
    insert_row(schema_conn, "Batches", dict(batch_id="FREE-001", part_no="P1", quantity=5, part_name="historical-copy-name",
                                          priority="normal", ready_status="no", status="pending", remark="keep-hidden"))
    insert_row(schema_conn, "BatchOperations", dict(op_code="FREE-001_01", batch_id="FREE-001", seq=1,
                op_type_id="OT1", op_type_name="turning", source="internal", setup_hours=None, unit_hours=0))
    schema_conn.commit()
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="batch-fixture-only")
    bp = Blueprint("workbench", __name__)
    register_batch_routes(bp)
    bp.add_url_rule("/api/workbench/v1/commands/<request_key>", view_func=command_receipt)
    app.register_blueprint(bp)

    @app.before_request
    def isolated_connection():
        g.db = schema_conn

    @app.after_request
    def private_response(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    client = app.test_client()
    client.batch_conn = schema_conn
    return client


def ref_for(client, kind="batch", key="FREE-001"):
    return client.batch_conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? AND active=1", (kind, key)).fetchone()[0]


def list_data(client, **scope):
    response = client.get(BASE, query_string=scope)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def detail(client, ref=None):
    response = client.get(BASE + "/" + (ref or ref_for(client)))
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def body(context, payload, key="batch-request-00000001"):
    return {"request_key": key, "write_token": context["write_token"], "input": payload}


def create_input(client, code="NEW-001"):
    return {"business_code": code, "part_ref": ref_for(client, "part", "P1"), "fields": {
        "quantity": 2, "due_date": None, "priority": "normal", "ready_status": "no", "ready_date": None, "remark": None}}


def post(client, action, payload, key="batch-request-00000001", ref=None, context=None):
    if action == "create":
        context = context or list_data(client)["data"]["create_context"]
        path = BASE + "/create"
    else:
        ref = ref or ref_for(client)
        context = context or detail(client, ref)["data"]["write_context"]
        path = BASE + "/" + ref + "/" + action
    return client.post(path, json=body(context, payload, key))


def state(client):
    return stored_state(client.batch_conn)


def assert_error(response, code, status=None):
    value = response.get_json()
    assert response.status_code == status if status else response.status_code >= 400
    assert value["ok"] is False and value["error"]["code"] == code, value
    assert value["committed"] is False, value
    return value

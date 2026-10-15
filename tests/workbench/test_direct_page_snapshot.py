"""Fresh calibration pagination keeps snapshot, detail and export bindings."""

from flask import Blueprint, Flask, g

from core.services.workbench.calibration.service import WorkbenchCalibrationService
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage_case  # noqa: F401
from web import public_token_registry
from web.routes.workbench.calibration import register_calibration_routes


def test_calibration_restores_page_once_and_keeps_scope_source_and_expiry(lineage_case, monkeypatch, record_property):
    case = lineage_case
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) "
                      "VALUES ('P1',2,'T1','second template','internal',0,2)")
    case.conn.commit()
    app = Flask("calibration-direct-page")
    app.config.update(TESTING=True, SECRET_KEY="temporary-calibration-direct-page")
    bp = Blueprint("calibration_direct_page", __name__)
    register_calibration_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def database():
        g.db = case.conn

    client, path, calls = app.test_client(), "/api/workbench/v1/calibration", []
    original = WorkbenchCalibrationService.read

    def captured(reader, query, **kwargs):
        calls.append(query.number)
        return original(reader, query, **kwargs)

    query = {"page": 2, "size": 1}
    before = case.conn.total_changes
    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchCalibrationService, "read", captured)
        response = client.get(path, query_string=query)
    assert response.status_code == 200, response.get_json()
    direct = response.get_json()
    assert calls == [2] and direct["data"]["page"]["number"] == 2
    assert direct["data"]["page"]["total"] == 2 and len(direct["data"]["items"]) == 1
    assert direct["meta"]["source"] == "production" and response.headers["Cache-Control"] == "no-store"
    record_property("direct_page", 2)
    record_property("fact_query_calls", len(calls))
    record_property("data_fields", sorted(direct["data"]))
    token = direct["meta"]["snapshot_ref"]
    repeated = client.get(path, query_string={**query, "snapshot_ref": token}).get_json()
    assert repeated["data"] == direct["data"] and repeated["meta"].keys() == direct["meta"].keys()
    assert repeated["meta"]["request_ref"] != direct["meta"]["request_ref"]
    assert all(repeated["meta"][key] == value for key, value in direct["meta"].items() if key != "request_ref")
    selected = direct["data"]["items"][0]["suggestion_ref"]
    for target in (path + "/export", path + "/" + selected):
        missing = client.get(target, query_string=query)
        assert missing.status_code == 400 and missing.get_json()["error"]["code"] == "snapshot_required"
        bound = client.get(target, query_string={**query, "snapshot_ref": token})
        assert bound.status_code == 200, bound.get_json()
    wrong_scope = client.get(path, query_string={**query, "source": "external", "snapshot_ref": token})
    assert wrong_scope.status_code == 409 and wrong_scope.get_json()["error"]["code"] == "snapshot_stale"
    now = public_token_registry.time.time()
    with monkeypatch.context() as patch:
        patch.setattr(public_token_registry.time, "time", lambda: now + 901)
        expired = client.get(path, query_string={**query, "snapshot_ref": token})
    assert expired.status_code == 409 and expired.get_json()["error"]["code"] == "snapshot_stale"
    assert case.conn.total_changes == before

from __future__ import annotations

from types import SimpleNamespace

from flask import Flask, g


class _Model(SimpleNamespace):
    def to_dict(self):
        return dict(self.__dict__)


def _build_app(monkeypatch):
    import web.routes.scheduler_batch_detail as route_mod

    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    app = Flask(__name__)
    app.secret_key = "aps-batch-detail-route"
    app.register_blueprint(route_mod.bp, url_prefix="/scheduler")
    return app


def test_scheduler_batch_detail_route_uses_request_services(monkeypatch) -> None:
    app = _build_app(monkeypatch)
    client = app.test_client()

    batch = _Model(
        batch_id="B001",
        part_no="P001",
        quantity=1,
        status="pending",
        priority="normal",
        ready_status="yes",
        remark=None,
    )
    op = _Model(
        id=1,
        batch_id="B001",
        source="internal",
        machine_id="M1",
        operator_id="O1",
        supplier_id=None,
    )
    machine = _Model(machine_id="M1", name="设备1", status="active")
    operator = _Model(operator_id="O1", name="人员1", status="active")
    supplier = _Model(supplier_id="S1", name="供应商1", status="active")

    services = SimpleNamespace(
        batch_service=SimpleNamespace(get=lambda batch_id: batch),
        schedule_service=SimpleNamespace(
            list_batch_operations=lambda batch_id: [op],
            get_external_merge_hint=lambda _op_id: None,
        ),
        machine_service=SimpleNamespace(
            list=lambda status=None: [machine],
            get_optional=lambda _mid: None,
        ),
        operator_service=SimpleNamespace(
            list=lambda status=None: [operator],
            get_optional=lambda _oid: None,
        ),
        supplier_service=SimpleNamespace(
            list=lambda status=None: [supplier],
            get_optional=lambda _sid: None,
        ),
        config_service=SimpleNamespace(get_snapshot=lambda: SimpleNamespace(prefer_primary_skill="yes")),
        operator_machine_query_service=SimpleNamespace(
            list_simple_rows_for_machine_operator_sets=lambda _machines, _operators: [
                {"machine_id": "M1", "operator_id": "O1", "skill_level": "normal", "is_primary": "yes"}
            ]
        ),
    )

    @app.before_request
    def _inject_services() -> None:
        g.services = services
        g.app_logger = app.logger
        g.op_logger = None

    response = client.get("/scheduler/batches/B001")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["batch"]["batch_id"] == "B001"
    assert payload["operations"][0]["machine_id"] == "M1"
    assert payload["machine_options"][0]["value"] == "M1"
    assert payload["operator_options"][0]["value"] == "O1"

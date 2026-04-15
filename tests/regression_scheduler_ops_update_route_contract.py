from __future__ import annotations

from types import SimpleNamespace

from flask import Flask, g

from core.infrastructure.errors import ValidationError
from web.error_handlers import register_error_handlers


class _ScheduleServiceSuccess:
    def __init__(self) -> None:
        self.saved = None

    def get_operation(self, op_id: int):
        return SimpleNamespace(id=op_id, batch_id="B001", source="internal")

    def update_internal_operation(self, **kwargs):
        self.saved = dict(kwargs)


class _ScheduleServiceMismatch:
    def get_operation(self, op_id: int):
        return SimpleNamespace(id=op_id, batch_id="B001", source="internal")

    def update_internal_operation(self, **kwargs):
        raise ValidationError("设备与人员不匹配", field="operator_id")


def _build_app(monkeypatch, schedule_service) -> Flask:
    import web.routes.scheduler_ops as route_mod

    monkeypatch.setattr(route_mod, "url_for", lambda endpoint, **kwargs: f"/{endpoint}/{kwargs.get('batch_id', '')}")

    app = Flask(__name__)
    app.secret_key = "aps-scheduler-ops-route"
    register_error_handlers(app)
    app.register_blueprint(route_mod.bp, url_prefix="/scheduler")

    @app.before_request
    def _inject_services() -> None:
        g.services = SimpleNamespace(schedule_service=schedule_service)
        g.app_logger = app.logger
        g.op_logger = None

    return app


def test_scheduler_ops_update_route_success_branch(monkeypatch) -> None:
    schedule_service = _ScheduleServiceSuccess()
    app = _build_app(monkeypatch, schedule_service)
    client = app.test_client()

    response = client.post(
        "/scheduler/ops/1/update",
        data={"machine_id": "M1", "operator_id": "O1", "setup_hours": "1.5", "unit_hours": "2.5"},
    )

    assert response.status_code in (301, 302)
    assert schedule_service.saved == {
        "op_id": 1,
        "machine_id": "M1",
        "operator_id": "O1",
        "setup_hours": "1.5",
        "unit_hours": "2.5",
    }


def test_scheduler_ops_update_route_rejects_machine_operator_mismatch(monkeypatch) -> None:
    app = _build_app(monkeypatch, _ScheduleServiceMismatch())
    client = app.test_client()

    response = client.post(
        "/scheduler/ops/1/update",
        data={"machine_id": "M1", "operator_id": "O9", "setup_hours": "1.5", "unit_hours": "2.5"},
        headers={"Accept": "application/json"},
    )

    payload = response.get_json()
    assert response.status_code == 400
    assert payload["error"]["message"] == "设备与人员不匹配"

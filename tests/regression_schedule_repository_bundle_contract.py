from __future__ import annotations

from dataclasses import fields
from types import SimpleNamespace

import core.services.scheduler.schedule_service as schedule_service_mod
from core.services.scheduler.repository_bundle import ScheduleRepositoryBundle


def test_schedule_repository_bundle_matches_schedule_service_repo_proxy_surface(monkeypatch) -> None:
    bundle_field_names = tuple(field.name for field in fields(ScheduleRepositoryBundle))
    sentinel_values = {name: object() for name in bundle_field_names}
    sentinel_bundle = SimpleNamespace(**sentinel_values)
    build_calls = {}

    def _fake_build(conn, *, logger=None):
        build_calls["conn"] = conn
        build_calls["logger"] = logger
        return sentinel_bundle

    monkeypatch.setattr(schedule_service_mod, "build_schedule_repository_bundle", _fake_build)

    conn = object()
    svc = schedule_service_mod.ScheduleService(conn, logger="logger-token", op_logger="op-token")

    service_repo_names = tuple(name for name in svc.__dict__ if name.endswith("_repo"))
    assert service_repo_names == bundle_field_names
    assert object.__getattribute__(svc, "_repos") is sentinel_bundle
    for name, expected in sentinel_values.items():
        assert getattr(svc, name) is expected
    assert build_calls == {"conn": conn, "logger": "logger-token"}

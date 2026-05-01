from __future__ import annotations

from app import create_app


def test_scheduler_routes_are_registered_by_factory() -> None:
    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/scheduler/run" in rules
    assert "/scheduler/gantt" in rules
    assert "/scheduler/analysis" in rules
    assert "/scheduler/resource-dispatch" in rules

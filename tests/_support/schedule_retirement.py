"""Retained schedule projections, separate from the retired public GET contract.

The test-only endpoint traverses the real request lifecycle and services, then
captures the original controller's render context. It does not restore a deleted
template, replace a public route or claim that its context is a rendered page.
"""

from __future__ import annotations

import json
from contextlib import closing
from dataclasses import asdict, is_dataclass
from typing import Any, Dict
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from tests._support.gantt_retirement import _business_state

_PROJECTION_ENDPOINT = "_schedule_projection_probe"
_PROJECTION_PATH = "/__schedule_projection_probe"
_RETAINED_ENDPOINTS = frozenset((
    "dashboard.index", "scheduler.batches_page", "scheduler.batch_detail", "scheduler.gantt_page",
    "scheduler.week_plan_page", "scheduler.resource_dispatch_page", "scheduler.analysis_page",
    "reports.index", "reports.overdue_page", "reports.execution_review_page", "system.history_page",
))


def initialize_read_fixture(app):
    """Finish documented pristine-store setup before measuring a request's writes."""
    from core.infrastructure.database import get_connection
    from core.services.scheduler.config.config_service import ConfigService
    from core.services.system.system_config_service import SystemConfigService
    from tests._support.sqlite_snapshot import table_rows

    with closing(get_connection(app.config["DATABASE_PATH"])) as conn:
        before = {name: table_rows(conn, name) for name in ("ScheduleConfig", "SystemConfig")}
        ConfigService(conn).get_snapshot()
        SystemConfigService(conn).ensure_defaults(backup_keep_days_default=app.config.get("BACKUP_KEEP_DAYS", 7))
        for name, rows in before.items():
            assert set(rows).issubset(set(table_rows(conn, name))), name


def _install_projection_probe(app):
    """Install one isolated dispatcher before this test app serves requests."""
    state = app.extensions.get(_PROJECTION_ENDPOINT)
    if state is not None:
        return state
    state = {}

    def dispatch():
        """Call only the retained controller selected by the current test."""
        return state["controller"](**state["path_values"])

    app.add_url_rule(_PROJECTION_PATH, endpoint=_PROJECTION_ENDPOINT, view_func=dispatch)
    app.extensions[_PROJECTION_ENDPOINT] = state
    return state


def capture_schedule_context(client, *, endpoint, path, template, path_values=None) -> Dict[str, Any]:
    """Read an original controller with real services, capturing only its sink."""
    app = client.application
    assert endpoint in _RETAINED_ENDPOINTS
    controller = app.view_functions[endpoint].__wrapped__
    assert controller.__module__.startswith(("web.routes.dashboard", "web.routes.domains.scheduler",
                                            "web.routes.reports", "web.routes.system_history"))
    state = _install_projection_probe(app)
    assert not state
    captured = []

    def capture(name, **context):
        """Preserve the entire actual context without pretending to render it."""
        assert name == template
        captured.append(context)
        return "schedule projection captured"

    before = _business_state(client)
    state.update(controller=controller, path_values=dict(path_values or {}))
    try:
        with patch.dict(controller.__globals__, {"render_template": capture}):
            response = client.get(_PROJECTION_PATH + "?" + urlsplit(path).query)
            assert response.status_code == 200, response.get_data(as_text=True)
            response.close()
        assert len(captured) == 1
        after = _business_state(client)
        assert after == before, {name: (before.get(name), after.get(name))
                                 for name in set(before) | set(after) if before.get(name) != after.get(name)}
        return captured[0]
    finally:
        state.clear()


def assert_retired_scope(client, path, *, message="没有改用", status=410):
    """A non-equivalent old scope must remain explicit and never change data."""
    before = _business_state(client)
    response = client.get(path)
    body = response.get_data(as_text=True)
    assert response.status_code == status, body
    assert message in body, body
    assert "Location" not in response.headers
    assert _business_state(client) == before
    response.close()
    return body


def projection_text(*items):
    """Read display values verbatim; do not filter or sanitize test evidence."""
    parts = []
    for item in items:
        if is_dataclass(item):
            assert not isinstance(item, type), "Display projection must be a dataclass instance"
            parts.append(projection_text(asdict(item)))
        elif isinstance(item, dict):
            parts.append(projection_text(*item.values()))
        elif isinstance(item, (tuple, list)):
            parts.append(projection_text(*item))
        elif item is not None:
            parts.append(str(item))
    return "\n".join(parts)


def assert_redirect_navigation(client, path, *, view, context):
    """Equivalent old input must carry exactly its original context to Workbench."""
    before = _business_state(client)
    response = client.get(path)
    assert response.status_code == 302, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    destination = urlsplit(response.headers["Location"])
    assert not destination.scheme and not destination.netloc and not destination.fragment
    assert destination.path == "/workbench"
    query = parse_qs(destination.query)
    assert set(query) == {"view", "nav"} and query["view"] == [view]
    assert json.loads(query["nav"][0]) == {"version": 1, "view": view, "context": context}
    assert _business_state(client) == before
    response.close()

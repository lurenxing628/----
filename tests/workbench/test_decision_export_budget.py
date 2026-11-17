"""Materialized downloads release the common read slot before encoding a file."""

import importlib
from contextlib import contextmanager
from datetime import datetime

import pytest
from flask import Flask, g

from core.models.workbench_action_values import FileDownload


@pytest.mark.parametrize("kind", ["run", "history"])
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_export_encodes_after_releasing_the_shared_plan_read_slot(monkeypatch, kind, fmt):
    routes = (importlib.import_module("web.routes.workbench.run_decision") if kind == "run" else
              importlib.import_module("web.routes.workbench.decision_history"))
    reader_owner = routes if kind == "run" else importlib.import_module("core.services.workbench.history.queries")
    writer_owner = routes if kind == "run" else importlib.import_module("core.services.workbench.history.export")
    reader_name = "read_decision_export" if kind == "run" else "read_history_all"
    writer_name = "write_run_decision_export" if kind == "run" else "write_history_export"
    active, steps = [], []

    @contextmanager
    def slot():
        active.append(True)
        try:
            yield
        finally:
            active.pop()

    def read(*_args, **_kwargs):
        assert active
        steps.append("read")
        snapshot = _kwargs["bind_snapshot"]({"saved": "scope"}, {"saved": "state"})
        return ({"saved": "rows"}, snapshot) if kind == "run" else ({"saved": "rows"}, snapshot, {"saved": "state"})

    moment = datetime(2026, 10, 18, 4, 0)

    def bind(scope, state, token, *, as_of, binding):
        assert active and scope == {"saved": "scope"} and state == {"saved": "state"} and token == "current"
        assert (as_of, binding) == (moment, "saved binding")
        steps.append("bind")
        return {"snapshot_ref": "current"}

    def write(data, snapshot, file_format, _section):
        assert fmt == file_format == "csv"
        assert not active and data == {"saved": "rows"} and snapshot == {"snapshot_ref": "current"}
        steps.append("encode")
        return FileDownload("saved.csv", "application/octet-stream", b"complete-saved-file", 17)

    def write_xlsx(writer, data, snapshot, _section):
        # The spawned encoder runs the route's own writer, the one CSV uses.
        assert fmt == "xlsx" and writer is write
        assert not active and data == {"saved": "rows"} and snapshot == {"snapshot_ref": "current"}
        steps.append("encode")
        return FileDownload("saved.xlsx", "application/octet-stream", b"complete-saved-file", 17)

    monkeypatch.setattr(routes.PLAN_READ_SLOTS, "slot", slot)
    monkeypatch.setattr(reader_owner, reader_name, read)
    monkeypatch.setattr(writer_owner, writer_name, write)
    monkeypatch.setattr(routes, "write_decision_xlsx", write_xlsx)
    read_context = importlib.import_module("web.routes.workbench.read_context")
    monkeypatch.setattr(read_context, "read_snapshot_time", lambda token: (moment, "saved binding"))
    monkeypatch.setattr(read_context, "bind_read_snapshot", bind)
    app = Flask(__name__)

    @app.before_request
    def connection():
        g.db = object()

    if kind == "run":
        app.add_url_rule("/export/<run_ref>", view_func=routes.run_decision_export)
        path = "/export/" + "a" * 48
    else:
        app.add_url_rule("/export", view_func=routes.decision_history_export)
        path = "/export"
    response = app.test_client().get(path, query_string={"format": fmt, "snapshot_ref": "current"})
    assert response.status_code == 200 and response.data == b"complete-saved-file"
    assert response.headers["X-Workbench-Row-Count"] == "17"
    assert steps == ["read", "bind", "encode"]

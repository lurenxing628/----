"""Shared canonical Gantt reads and business-state checks for retirement tests."""

from __future__ import annotations

import json
from contextlib import closing
from html.parser import HTMLParser

from core.infrastructure.database import get_connection


class _Boot(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active, self.parts = False, []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "workbench-boot":
            self.active = True

    def handle_data(self, value):
        if self.active:
            self.parts.append(value)

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False


def _business_state(client):
    with closing(get_connection(client.application.config["DATABASE_PATH"])) as conn:
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                  if row[0] not in ("OperationLogs", "sqlite_sequence", "SystemJobState")]
        return {name: sorted(repr(tuple(row)) for row in conn.execute('SELECT * FROM "' + name.replace('"', '""') + '"'))
                for name in tables}


def _canonical_workspace(client, query):
    response = client.get("/scheduler/gantt", query_string=query)
    assert response.status_code == 302, response.get_data(as_text=True)
    target = response.headers["Location"]
    canonical = client.get(target)
    assert canonical.status_code == 200, canonical.get_data(as_text=True)
    parser = _Boot()
    parser.feed(canonical.get_data(as_text=True))
    navigation = json.loads("".join(parser.parts))["navigation"]
    assert navigation["view"] == "gantt"
    context = navigation["context"]
    reference = context["plan_ref"]
    scope = {key: value for key, value in context.items() if key != "plan_ref"}
    workspace = client.get("/api/workbench/v1/plans/" + reference + "/workspace", query_string=scope)
    assert workspace.status_code == 200, workspace.get_data(as_text=True)
    payload = workspace.get_json()
    assert payload["ok"] and payload["data"]["plan"]["plan_ref"] == reference
    assert payload["meta"]["source"] == "production" and payload["meta"]["time_basis"] == "factory_local"
    # Refresh must resolve the same original ref, not the most recent plan.
    refreshed = client.get(target)
    again = _Boot()
    again.feed(refreshed.get_data(as_text=True))
    assert json.loads("".join(again.parts))["navigation"] == navigation
    return context, payload

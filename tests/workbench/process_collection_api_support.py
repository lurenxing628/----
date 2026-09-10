"""Real process HTTP requests, complete SQLite oracles and browser contracts."""

import json
import shutil
import subprocess
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

from core.services.workbench.process_queries import WorkbenchProcessQueryService
from tests.workbench.process_query_support import seed_process
from tests.workbench.process_stage_api_support import BASE, StageAPI, rejected, seed_history, success

CREATE = {"business_code": "API-NEW", "label": "New part", "route_raw": " 10turning\r\n20unknown ", "remark": " note "}
LIST = BASE + "/entities/part"
COLLECTION = BASE + "/process/parts/"
TABLE = BASE + "/process-table/"


@pytest.fixture(name="collection_api")
def collection_api_fixture(app_client):
    api = CollectionAPI(app_client)
    with api.database() as conn:
        seed_process(conn)
        seed_history(conn)
    return api


def transport(scope):
    return {key: json.dumps(value) if isinstance(value, (dict, list)) else value
            for key, value in scope.items() if value is not None}


def conditions(column, keys, mode="include"):
    return {column: {"mode": mode, "values": list(keys)}}


class CollectionAPI(StageAPI):
    def listing(self, scope=None, **page):
        return success(self.client.get(LIST, query_string=transport({**(scope or {}), **page})))

    def facet_response(self, column="label", scope=None, *, selection=False, **page):
        path = TABLE + ("facet-selection/" if selection else "facets/") + column
        return self.client.get(path, query_string={"scope": json.dumps(scope or {}), **page})

    def facet(self, column="label", scope=None, *, selection=False, **page):
        return success(self.facet_response(column, scope, selection=selection, **page))

    def bound(self, refs, scope=None, size=20):
        scope = {} if scope is None else scope
        listing = self.listing(scope, size=size)
        return {"refs": refs, "scope": scope, "page_size": size, "snapshot_ref": listing["meta"]["snapshot_ref"]}

    def send(self, action, body):
        return self.client.post(COLLECTION + action, json=body)

    def create_body(self, payload=None):
        context = self.listing()["data"]["create_context"]
        return {"request_key": "process-api-" + uuid.uuid4().hex, "write_token": context["write_token"],
                "input": dict(CREATE if payload is None else payload)}

    def delete_body(self, refs=None, scope=None, size=20):
        request = self.bound(refs or [self.ref(code="PROC-002"), self.ref(code="PROC-003")], scope, size)
        preview = success(self.send("bulk-preview", request))["data"]
        return {"request_key": "process-api-" + uuid.uuid4().hex,
                "write_token": preview["write_context"]["write_token"], "input": {"preview_ref": preview["preview_ref"]}}


def enforce_readonly(monkeypatch):
    original = WorkbenchProcessQueryService.read_snapshot
    seen = []

    @contextmanager
    def readonly(self):
        changes = self.conn.total_changes
        self.conn.execute("PRAGMA query_only=ON")
        try:
            with original(self) as state:
                yield state
            assert self.conn.total_changes == changes
            seen.append(True)
        finally:
            self.conn.execute("PRAGMA query_only=OFF")

    monkeypatch.setattr(WorkbenchProcessQueryService, "read_snapshot", readonly)
    return seen


def expire(api, namespace, token):
    registry = api.client.application.extensions["aps_public_opaque_tokens"]
    registry[namespace]["tokens"][token]["expires_at"] = 0


def browser_contract(mode, raw, request=None, *, intent=None, refs=None):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required to run the existing browser contracts without Chrome")
    script = """
const fs = require('node:fs'), vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8')), context = {};
context.window = context; vm.createContext(context);
for (const file of ['resource-contract.js', 'ResourceTableFilterModel.js', 'ResourceMaterialContract.js',
                    'ProcessContract.js', 'ProcessActionContract.js'])
  vm.runInContext(fs.readFileSync('frontend/workbench/app/' + file, 'utf8'), context, { filename: file });
try {
  const A = context.APSProcessActions, P = context.APSProcessContract, M = context.ResourceTableFilterModel;
  if (input.mode === 'delete') A.deletePreview(input.raw, input.request);
  else if (input.mode === 'receipt') A.receipt(input.raw, input.intent, input.refs);
  else if (input.mode === 'list') P.list(input.raw, input.request);
  else M[input.mode](input.raw, input.request);
} catch (error) { throw new Error(String(error.message) + ' ' + JSON.stringify(error)); }
"""
    result = subprocess.run([node, "-e", script], input=json.dumps({"mode": mode, "raw": raw, "request": request,
        "intent": intent, "refs": refs}), text=True, capture_output=True, timeout=30,
        cwd=str(Path(__file__).resolve().parents[2]))
    assert result.returncode == 0, result.stderr


def seed_table_rows(api, count, prefix="TABLE-"):
    with api.database() as conn:
        conn.executemany("INSERT INTO Parts(part_no,part_name,route_raw) VALUES (?,?,?)",
                         [(prefix + f"{index:05d}", "Name " + f"{index:05d}", "OnlyRouteToken") for index in range(count)])
    return [prefix + f"{index:05d}" for index in range(count)]

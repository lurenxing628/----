"""Real file endpoints, isolated SQLite and the production Node contract."""

import json
import shutil
import subprocess
import uuid
from io import BytesIO
from pathlib import Path

import pytest

from core.services.workbench.process_file_codec import encode_process_file
from tests.workbench.process_query_support import seed_process
from tests.workbench.process_stage_api_support import BASE, PART, StageAPI, seed_history, success

ROOT = Path(__file__).resolve().parents[2]


def uncertain_failure(response):
    body = response.get_json()
    assert response.status_code == 500 and body["ok"] is False, body
    assert body["committed"] == "unknown" and body["error"]["code"] == "storage_failure", body
    assert response.headers["Cache-Control"] == "no-store"
    return body["error"]


@pytest.fixture(name="file_api")
def file_api_fixture(app_client):
    api = FileAPI(app_client)
    with api.database() as conn:
        seed_process(conn)
        seed_history(conn)
    return api


class FileAPI(StageAPI):
    def file_post(self, kind, action, body):
        return self.client.post(BASE + "/process-files/" + kind + "/" + action, json=body)

    def upload(self, kind, content, fmt="csv", target=None, **extra):
        data = {"file": (BytesIO(content), "input." + fmt), "format": fmt, "mode": "upsert"}
        if target is not None:
            data["target_ref"] = target
        data.update(extra)
        return self.client.post(BASE + "/process-files/" + kind + "/preview", data=data)

    def preview_rows(self, kind, rows, fmt="csv", target=None):
        return success(self.upload(kind, encode_process_file(kind, rows, fmt).content, fmt, target))

    def file_body(self, preview, *, groups=None, zero=False):
        data = preview["data"]
        return {"request_key": "file-api-" + uuid.uuid4().hex, "write_token": data["write_context"]["write_token"],
                "input": {"preview_ref": data["preview_ref"], "discard_group_refs": groups or [],
                          "confirm_zero_unit_hours": zero}}

    def file_intent(self, kind, fmt="csv", target=None):
        if kind == "hours":
            self.prepare()
            rows = [{"business_code": PART, "sequence": 10, "unit_hours": 2},
                    {"business_code": PART, "sequence": 30, "unit_hours": 3}]
        else:
            rows = [{"business_code": PART, "label": "Changed label", "remark": "Changed remark"}]
            if target is None:
                rows.append({"business_code": "FILE-NEW", "label": "New part", "route_raw": "10\u8f66\u524a"})
        preview = self.preview_rows(kind, rows, fmt, target)
        assert preview["data"]["can_confirm"], preview
        return preview, self.file_body(preview)

    def export_body(self, *, scope=None, fmt="csv", selection="all", refs=None, target=None, size=2):
        scope = {} if scope is None else scope
        if target is None:
            query = {key: json.dumps(value) if isinstance(value, (list, dict)) else value
                     for key, value in scope.items() if value is not None}
            listed = success(self.client.get(BASE + "/entities/part", query_string={**query, "size": size}))
        else:
            listed = success(self.client.get(BASE + "/entities/part/" + target))
        body = {"format": fmt, "selection": selection, "scope": scope, "page_size": size,
                "snapshot_ref": listed["meta"]["snapshot_ref"]}
        if refs is not None:
            body["refs"] = refs
        if target is not None:
            body["target_ref"] = target
        return body, listed

    def download(self, kind, export_ref, **extra):
        return self.client.get(BASE + "/process-files/" + kind + "/export",
                               query_string={"export_ref": export_ref, **extra})

    def export(self, kind, **options):
        body, listed = self.export_body(**options)
        preview = success(self.file_post(kind, "export-preview", body))
        download = self.download(kind, preview["data"]["export_ref"])
        assert download.status_code == 200, download.get_json()
        assert download.headers["Cache-Control"] == "no-store"
        assert download.headers["X-Workbench-Snapshot-Ref"] == body["snapshot_ref"]
        assert download.headers["X-Workbench-As-Of"] == listed["meta"]["as_of"]
        return body, preview, download


def node_contract(mode, raw, kind, *, body=None, preview=None, target=None, fmt="csv"):
    node = shutil.which("node")
    assert node, "Node is required to check real API responses against ProcessFileContract.js"
    script = r"""
const fs = require('fs'), vm = require('vm'), path = require('path'), assert = require('assert/strict');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const ctx = { console, window: null }; ctx.window = ctx; vm.createContext(ctx);
for (const name of ['resource-contract.js', 'ResourceTableFilterModel.js', 'ResourceMaterialContract.js',
  'ProcessContract.js', 'ProcessActionContract.js', 'ProcessFileContract.js'])
  vm.runInContext(fs.readFileSync(path.join(input.root, 'frontend/workbench/app', name), 'utf8'), ctx);
const F = ctx.APSProcessFiles, calls = [];
ctx.APSResourceAPI = { create: () => Object.fromEntries(['query', 'execute', 'preview', 'download'].map(
  method => [method, (...args) => calls.push({ method, args })])) };
vm.runInContext(fs.readFileSync(path.join(input.root, 'frontend/workbench/app/ProcessAPI.js'), 'utf8'), ctx);
const api = ctx.APSProcessAPI.create(), plain = value => JSON.parse(JSON.stringify(value));
if (input.mode === 'export-body') {
  console.log(JSON.stringify(F.exportBody(input.body, input.body.selection, input.body.format)));
} else if (input.mode === 'preview') {
  F.preview(input.raw, input.kind, input.fmt, { target_ref: input.target });
  api.filePreview(input.kind, 'import', {});
  assert.equal(calls[0].args[0], 'process-files/' + input.kind + '/preview');
} else if (input.mode === 'export') {
  F.exportPreview(input.raw, input.kind, input.body);
  api.fileDownload(input.kind, false, { export_ref: input.raw.data.export_ref });
  assert.deepEqual(plain(calls[0].args[1]), { export_ref: input.raw.data.export_ref });
  assert.equal(calls[0].args[0], 'process-files/' + input.kind + '/export');
} else {
  const intent = { kind: 'process_' + input.kind + '_import', action: 'confirm', ref: input.body.input.preview_ref };
  F.receipt(input.raw, intent, input.kind, input.preview.data, input.target);
  assert(!('stage' in input.raw.data));
  assert(input.raw.data.rows.every(row => !('stage' in row)));
  api.command(intent.kind, intent.action, intent.ref, input.body);
  assert.equal(calls[0].args[0], 'process-files/' + input.kind + '/confirm');
  assert.deepEqual(plain(calls[0].args[1]), input.body);
}
if (input.mode !== 'export-body') console.log('real-process-file-contract:' + input.mode + ':' + input.kind);
"""
    value = {"root": str(ROOT), "mode": mode, "raw": raw, "kind": kind, "body": body,
             "preview": preview, "target": target, "fmt": fmt}
    result = subprocess.run([node, "-e", script], input=json.dumps(value), text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout) if mode == "export-body" else result.stdout.strip()

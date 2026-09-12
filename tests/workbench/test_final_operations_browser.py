"""Whole main page, four real Chromium variants, SQL and downloaded payloads."""

import csv
import io
import json
import subprocess
import zipfile
from contextlib import closing

import pytest

from core.infrastructure.database import get_connection
from tests.workbench.final_operations_seed import seed
from tests.workbench.final_operations_support import REPO, OperationsHost, digest, runtime_tools
from tests.workbench.system_restore_entrypoint_support import wait_for

REQUEST_BINDING_PROBE = r"""
const assert = require('node:assert/strict'), { EventEmitter } = require('node:events');
const { support } = require(process.argv[1]);
class Page extends EventEmitter {
  wait(kind, predicate) {
    return new Promise(resolve => {
      const listener = value => { if (predicate(value)) { this.off(kind, listener); resolve(value); } };
      this.on(kind, listener);
    });
  }
  waitForRequest(predicate) { return this.wait('request', predicate); }
  waitForResponse(predicate) { return this.wait('response', predicate); }
}
(async () => {
  const cases = ['get', 'post', 'wrong-status', 'missing-response', 'body-error', 'query-scope'];
  for (const mode of cases) {
    const page = new Page(), reads = [], method = mode === 'post' ? 'POST' : 'GET';
    const expected = mode === 'post' ? 422 : 200, bodyError = new Error('Current response body failed');
    function response(name, verb = method, suffix = '/dashboard') {
      const query = mode === 'query-scope' ? name === 'current' ? '?page_size=25' : '?page_size=10' : '';
      const request = { url: () => 'http://127.0.0.1/api/workbench/v1' + suffix + query, method: () => verb,
        response: async () => mode === 'missing-response' && name === 'current' ? null : value };
      const value = { url: request.url, request: () => request,
        status: () => mode === 'wrong-status' && name === 'current' ? 503 : expected,
        text: async () => { reads.push(name); if (name === 'old') throw new Error('Old aborted response body');
          if (mode === 'body-error' && name === 'current') throw bodyError;
          return JSON.stringify({ request: name }); },
        json: async () => JSON.parse(await value.text()) };
      return value;
    }
    const old = response('old'), current = response('current');
    const decoys = [response('wrong-method', method === 'GET' ? 'POST' : 'GET'), response('wrong-path', method, '/unrelated')];
    if (mode === 'query-scope') decoys.push(response('wrong-query'));
    page.emit('request', old.request());
    const h = support(page, {}, {});
    let actions = 0;
    const result = h.request('/dashboard', async () => {
      actions++;
      for (const value of decoys) { page.emit('request', value.request()); page.emit('response', value); }
      page.emit('response', old);
      page.emit('request', current.request()); page.emit('response', current);
    }, expected, method, mode === 'query-scope' ? { page_size: 25 } : null);
    if (mode === 'wrong-status') await assert.rejects(result, error => error.code === 'ERR_ASSERTION' && error.actual === 503 && error.expected === 200);
    else if (mode === 'missing-response') await assert.rejects(result, /action request ended without a response/);
    else if (mode === 'body-error') await assert.rejects(result, error => error === bodyError);
    else assert.deepEqual(await result, { request: 'current' });
    assert.equal(actions, 1);
    assert(reads.every(name => name === 'current'));
  }
  process.stdout.write(JSON.stringify({ cases, old_response_bodies_read: 0, repeated_actions: 0 }));
})().catch(error => { console.error(error); process.exitCode = 1; });
"""


@pytest.mark.parametrize("width,theme", [(1920, "light"), (1920, "dark"), (1392, "light"), (1392, "dark")])
def test_final_operations_main_controls_and_persistence(tmp_path, width, theme):
    binding = subprocess.run([runtime_tools()[0], "-e", REQUEST_BINDING_PROBE,
                              str(REPO / "tests/workbench/final_operations_browser_support.cjs")],
                             text=True, capture_output=True, timeout=20)
    (tmp_path / "request-binding-proof.json").write_text(binding.stdout, encoding="utf-8")
    assert binding.returncode == 0, binding.stderr
    assert len(json.loads(binding.stdout)["cases"]) == 6
    host = OperationsHost(tmp_path / f"operations-{width}-{theme}")
    seed(host.root, include_candidate_baseline=True)
    try:
        host.start()
        wait_for(lambda: host.stored("SELECT state FROM WorkbenchRunJobs")[0]["state"] == "complete", timeout=60)
        original = {table: host.stored('SELECT * FROM "' + table + '" ORDER BY rowid') for table in (
            "Batches", "BatchOperations", "Schedule", "ScheduleHistory", "BatchMaterials", "MachineDowntimes", "OperationExecutionEvents", "WorkbenchProductionReports")}
        report = host.probe("normal", width, theme)
        for table, rows in original.items():
            assert host.stored('SELECT * FROM "' + table + '" ORDER BY rowid') == rows
        assert len(host.stored("SELECT * FROM WorkbenchDashboardHistory")) == 3
        assert len(host.stored("SELECT * FROM WorkbenchDashboardExternalHistory")) == 3
        assert len(host.stored("SELECT * FROM WorkbenchOutsourcingFacts")) == 3
        for field, value in report["config_fields"].items():
            assert host.stored("SELECT config_value FROM SystemConfig WHERE config_key=?", (field,))[0]["config_value"] == value
        receipts = host.stored("SELECT request_key FROM WorkbenchCommandReceipts WHERE action='system.config.save'")
        assert receipts == [{"request_key": report["config_pending"]["request_key"]}]
        assert not (host.backups / report["created_backup"]["filename"]).exists()
        assert report["deleted_backup"]["state"] == "succeeded"
        directory = host.root / f"probe-normal-{width}-{theme}"
        assert digest(directory / "created-backup-payload.db") == report["created_payload_sha256"]
        assert digest(directory / report["created_backup"]["filename"]) == report["created_payload_sha256"]
        with closing(get_connection(str(directory / "created-backup-payload.db"))) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert conn.execute("SELECT config_value FROM SystemConfig WHERE config_key='FINAL_OPERATIONS'").fetchone()[0] == "current"
            assert conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingFacts").fetchone()[0] == 3
        rows = list(csv.reader(io.StringIO((directory / "logs.csv").read_text(encoding="utf-8-sig"))))
        assert sum(any("F operation row" in cell for cell in row) for row in rows) == 31
        with zipfile.ZipFile(str(directory / "logs.zip")) as archive:
            assert archive.testzip() is None
            assert "diagnostic_info.json" in archive.namelist()
            manifest = json.loads(archive.read("diagnostic_info.json"))
            assert manifest["scope"] == "sanitized-log-windows" and manifest["rows"] == 31
            assert archive.read("logs.csv") == (directory / "logs.csv").read_bytes()
        before = set(host.backups.glob("*.db"))
        host.stop()
        after = set(host.backups.glob("*.db"))
        assert after - before, "Enabled ordinary exit backup must create an actual database file"
        evidence = json.loads((host.root / "process-evidence.json").read_text())
        assert not evidence["violations"]
        initial = json.loads((host.root / "source-at-create.json").read_text())
        assert all(evidence["sources"][path] == value for path, value in initial.items())
        assert all(digest(REPO / row["path"]) == row["sha256"] for row in host.assets["source_inputs"])
        assert host.marker() == "current"
        (host.root / "first-process-evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
        first_pid = evidence["pid"]
        host.start()
        assert host.ready["pid"] != first_pid
        status, saved = host.request("/api/workbench/v1/system/config")
        expected_values = {key: value if key.endswith("_enabled") else int(value) for key, value in report["config_fields"].items()}
        assert status == 200 and saved["data"]["values"] == expected_values
        assert saved["data"]["stored_values"] == report["config_fields"]
        status, replay = host.request("/api/workbench/v1/system/results/" + receipts[0]["request_key"])
        assert status == 200 and replay["data"]["command"]["replayed"] is True
        assert replay["data"]["command"]["receipt_ref"] == report["config_committed_response"]["receipt_ref"]
        assert host.stored("SELECT request_key FROM WorkbenchCommandReceipts WHERE action='system.config.save'") == receipts
        restarted_ui = host.probe("read-controls", width, theme, expected_config_fields=report["config_fields"])
        assert restarted_ui["config_restart_values"] == report["config_fields"]
        assert not [row for row in restarted_ui["responses"] if row["method"] not in ("GET", "HEAD")]
        host.stop()
        restarted = json.loads((host.root / "process-evidence.json").read_text())
        assert not restarted["violations"]
        (host.root / "config-restart-proof.json").write_text(json.dumps({"first_pid": first_pid, "second_pid": restarted["pid"],
            "config": saved, "original_receipt": replay, "config_receipt_count": len(receipts)}), encoding="utf-8")
        (host.root / "sql-proof.json").write_text(json.dumps({"source_tables_retained": list(original), "config_request_key": receipts[0]["request_key"],
            "downloaded_log_rows": 31, "exit_backup_files": [str(path) for path in after - before], "source_hashes": evidence["sources"]}, indent=2), encoding="utf-8")
    finally:
        host.close()

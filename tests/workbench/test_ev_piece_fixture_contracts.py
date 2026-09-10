"""EV-only small consumer checks: frozen JS, real temporary DTOs, no shared build."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_run_candidate_baseline_support import api, original_plan
from tests.workbench.test_run_candidate_support import candidate_case as candidate_case  # noqa: F401
from tests.workbench.test_run_candidate_support import compute, read, retained

ROOT = Path(os.environ.get("WORKBENCH_EV_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
SOURCES = ["frontend/workbench/app/" + name for name in (
    "resource-contract.js", "PointContract.js", "PlanProcessOrder.js", "PlanContract.js", "PointGanttModel.js",
    "PlanGanttModel.js", "RunCandidateAPI.js", "RunCandidateModel.js", "RunBaselineAPI.js", "RunBaselineModel.js",
)] + ["tests/workbench/plan_ui_fixtures.cjs"]
BOOT = r"""
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8')), ctx = {window: {}, Date};
for (const file of input.sources.filter(p => p.startsWith('frontend/')))
  vm.runInNewContext(fs.readFileSync(file, 'utf8'), ctx, {filename: file});
const W = ctx.window, clone = v => JSON.parse(JSON.stringify(v));
const fields = ['piece_id', 'quantity', 'batch_quantity', 'quantity_basis', 'quantity_reason'];
"""
MODEL = r"""
const F = require(process.cwd() + '/tests/workbench/plan_ui_fixtures.cjs');
let checks = 0;
for (const n of [1, 2, 3]) for (const scope of [{}, {range_start: '2026-09-09T23:00:00', range_end: '2026-09-10T01:00:00'},
  {range_start: '2026-10-01T00:00:00', range_end: '2026-10-02T00:00:00'}]) {
  const payload = F.workspace(F.ref(n), scope), before = JSON.stringify(payload);
  const data = W.APSPlanContract.workspace(payload, F.ref(n), scope).data;
  const baseline = data.projections.baseline;
  const tasks = data.tasks.concat(baseline.items.flatMap(row => [row.before, row.after]).filter(Boolean));
  for (const task of tasks) assert.deepEqual(fields.map(key => task[key]), [null, null, null, 'unknown', 'plan_target_not_recorded']);
  for (const mode of ['machine', 'operator', 'batch']) {
    const model = W.PlanGanttModel.layout(data, mode, '', true);
    for (const task of tasks) if (data.scope.range_start === null || data.tasks.includes(task))
      assert(model.locations.has(task.task_ref));
  }
  for (const row of baseline.items) if (row.after_in_scope)
    assert.deepEqual(row.after, data.tasks.find(task => task.task_ref === row.after.task_ref));
  assert.equal(JSON.stringify(payload), before);
  if (data.tasks.length) for (const key of fields) {
    const bad = clone(payload); delete bad.data.tasks[0][key];
    assert.throws(() => W.APSPlanContract.workspace(bad, F.ref(n), scope)); checks++;
  }
  if (data.tasks.length) for (const patch of [{quantity: 0}, {batch_quantity: 3}, {quantity_reason: null}]) {
    const bad = clone(payload); Object.assign(bad.data.tasks[0], patch);
    assert.throws(() => W.APSPlanContract.workspace(bad, F.ref(n), scope)); checks++;
  }
  checks++;
}
console.log(JSON.stringify({checks, capacity_run: false}));
"""
REAL = r"""
let checks = 0;
for (const fixture of input.fixtures) {
  const before = JSON.stringify(fixture), A = W.RunCandidateAPI, B = W.RunBaselineAPI;
  const data = A.workspace(fixture.workspace, input.candidate_ref, fixture.scope, input.run_ref);
  const baseline = B.validate(fixture.baseline, data);
  const candidateRows = data.tasks.concat(data.unplanned_operations);
  for (const row of candidateRows.concat(baseline.comparisons)) {
    const expected = input.quantities[row.batch_label];
    assert.deepEqual([row.piece_id, row.quantity, row.batch_quantity], [null, expected, expected]);
    assert.equal(row.quantity, row.execution_at_generation.target_quantity);
    assert.equal(row.execution_at_generation.target_basis, 'batch');
  }
  W.RunBaselineModel.compose(W.RunCandidateModel.layout(data, 'machine', ''), baseline, 'machine', '');
  assert.equal(JSON.stringify(fixture), before);
  for (const collection of ['tasks', 'unplanned_operations']) if (data[collection].length) {
    for (const key of ['piece_id', 'batch_quantity']) {
      const bad = clone(fixture.workspace); delete bad.data[collection][0][key];
      assert.throws(() => A.workspace(bad, input.candidate_ref, fixture.scope, input.run_ref)); checks++;
    }
    const bad = clone(fixture.workspace); bad.data[collection][0].quantity++;
    assert.throws(() => A.workspace(bad, input.candidate_ref, fixture.scope, input.run_ref)); checks++;
  }
  for (const key of ['piece_id', 'batch_quantity']) {
    const bad = clone(fixture.baseline); delete bad.data.comparisons[0][key];
    assert.throws(() => B.validate(bad, data)); checks++;
  }
  if (data.tasks.length) {
    const bad = clone(fixture.baseline), row = bad.data.comparisons.find(r => r.operation_ref === data.tasks[0].operation_ref);
    row.batch_quantity++;
    assert.throws(() => B.validate(bad, data)); checks++;
  }
  checks++;
}
console.log(JSON.stringify({checks, source: 'real temporary API DTOs', capacity_run: false}));
"""


def probe(tmp_path, script, payload=None):
    frozen = tmp_path / "frozen"
    fingerprints = {}
    for name in SOURCES:
        source, target = ROOT / name, frozen / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(target))
        fingerprints[name] = hashlib.sha256(target.read_bytes()).hexdigest()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == fingerprints[name]
    node, _, modules = runtime_tools()
    result = subprocess.run([node, "-e", BOOT + script], cwd=str(frozen),
        input=json.dumps(dict(payload or {}, sources=SOURCES)), text=True, capture_output=True, timeout=30,
        env=dict(os.environ, NODE_PATH=modules))
    for name, digest in fingerprints.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    assert result.returncode == 0, result.stdout + result.stderr
    report = dict(json.loads(result.stdout), sources=fingerprints)
    (tmp_path / "ev-consumer-evidence.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def test_small_plan_legacy_fixtures_keep_unknown_metadata(tmp_path):
    assert probe(tmp_path, MODEL)["checks"] == 57


def test_real_candidate_baseline_metadata_matches_captured_targets(candidate_case, tmp_path):
    case = candidate_case
    case.batch("ZERO", quantity=0, ready_status="no")
    case.operation("ZERO")
    case.batch("OUTSIDE", quantity=5)
    outside = case.operation("OUTSIDE")
    original_plan(case, [case.op_id, outside], start="2026-09-12T08:00:00", end="2026-09-12T10:00:00")
    run_ref, refs = compute(case, case.settings("B1", "ZERO"))
    client, _ = api(case)
    fixtures = []
    with retained(case.conn):
        for scope in ({}, {"range_start": "2026-09-12T08:01:00", "range_end": "2026-09-12T08:02:00"}):
            fixtures.append({"scope": scope, "workspace": read(client, "/candidates/" + refs[0] + "/workspace", **scope),
                             "baseline": read(client, "/candidates/" + refs[0] + "/baseline", **scope)})
        report = probe(tmp_path, REAL, {"fixtures": fixtures, "run_ref": run_ref, "candidate_ref": refs[0],
                                     "quantities": {"B1": 3, "ZERO": 0, "OUTSIDE": 5}})
    assert report["checks"] == 16

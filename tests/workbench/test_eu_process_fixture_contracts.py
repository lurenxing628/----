"""EU: existing mock DTOs must agree with real SQLite projections and JS contracts."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.workbench.merged_cycle_projection_support import (
    merged_cycle_application as _merged_cycle_application,  # noqa: F401
)
from tests.workbench.merged_cycle_projection_support import (
    operation,
    readonly_detail,
)

ROOT = Path(__file__).resolve().parents[2]
NODE_PROBE = r"""
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const babel = require('./frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js');
const ast = babel.transform(fs.readFileSync(input.path, 'utf8'), {ast:true, code:false}).ast;
const declarations = ast.program.body.filter(row => row.type === 'VariableDeclaration').flatMap(row => row.declarations);
const node = declarations.find(row => row.id.name === input.variable);
assert(node && node.init.type === 'TemplateLiteral');
assert.equal(node.init.expressions.length, 0, 'Fixture must be extracted exactly, without evaluating the browser runner');
const context = {sessionStorage:{getItem:()=>null}, document:{addEventListener:()=>{}}};
context.window = context; vm.createContext(context);
for (const file of ['resource-contract.js', 'ProcessContract.js'])
  vm.runInContext(fs.readFileSync('frontend/workbench/app/' + file, 'utf8'), context);
vm.runInContext(node.init.quasis[0].value.cooked, context);
const raw = vm.runInContext(input.expression, context);
const accept = value => context.APSProcessContract.detail(value, value.data.ref);
accept(raw);
for (const row of raw.data.operations) {
  const missing = JSON.parse(JSON.stringify(raw));
  delete missing.data.operations.find(item => item.ref === row.ref).external_days_source;
  assert.throws(() => accept(missing), 'Missing source cannot pass the real contract');
}
const internal = raw.data.operations.find(row => row.source === 'internal');
if (internal) {
  const fake = JSON.parse(JSON.stringify(raw));
  fake.data.operations.find(row => row.ref === internal.ref).external_days_source = 'group';
  assert.throws(() => accept(fake), 'Internal operations cannot claim a group cycle');
}
console.log(JSON.stringify(raw.data));
"""


def fixture_detail(filename, variable, expression):
    node = shutil.which("node")
    assert node, "Node is required to verify the actual ProcessContract.js"
    run = subprocess.run(
        [node, "-e", NODE_PROBE], cwd=str(ROOT), text=True, capture_output=True, timeout=30,
        input=json.dumps({"path": "tests/workbench/" + filename, "variable": variable, "expression": expression}),
    )
    assert run.returncode == 0, run.stdout + run.stderr
    return json.loads(run.stdout)


def cycle(row):
    return row["external_days"], row["external_days_source"]


@pytest.mark.parametrize("stage", ("source", "hours", "ready"))
def test_eu_process_detail_internal_source_is_explicit_null(merged_cycle_api, stage):
    data = fixture_detail("process_detail_files_probe.cjs", "fixture",
                          "f={revision:1}; env(part(" + json.dumps(stage) + "))")
    expected = cycle(operation(readonly_detail(merged_cycle_api), 10))
    assert expected == (None, None)
    assert all(cycle(row) == expected for row in data["operations"])


def test_eu_process_read_mock_preserves_invalid_zero_projection(merged_cycle_api):
    merged_cycle_api.execute("UPDATE PartOperations SET ext_days=0 WHERE part_no='PROC-001' AND seq=20")
    merged_cycle_api.execute("UPDATE ExternalGroups SET total_days=0 WHERE group_id='PROC-G'")
    real = readonly_detail(merged_cycle_api)
    data = fixture_detail("process_widgets_probe.cjs", "fixtureCode", "envelope(detailPart(1))")
    actual, expected = data["operations"][1], operation(real)
    assert cycle(actual) == cycle(expected) == (None, None)
    assert actual["issues"] == expected["issues"]
    group = next(row for row in real["external_groups"] if row["ref"] == expected["external_group_ref"])
    assert data["external_groups"][0]["total_days"] is group["total_days"] is None
    assert data["external_groups"][0]["issues"] == group["issues"]
    assert {row["code"] for row in actual["issues"]} == {"value_invalid", "external_group_invalid"}
    assert merged_cycle_api.rows("PartOperations", "part_no='PROC-001' AND seq=20")[0]["ext_days"] == 0
    assert merged_cycle_api.rows("ExternalGroups", "group_id='PROC-G'")[0]["total_days"] == 0


@pytest.mark.parametrize("stage", ("route", "source", "hours", "ready"))
def test_eu_process_stage_existing_cycle_is_operation_not_group(merged_cycle_api, stage):
    merged_cycle_api.execute("UPDATE PartOperations SET ext_days=2 WHERE part_no='PROC-001' AND seq=20")
    data = fixture_detail("process_stage_widgets_probe.cjs", "fixture",
                          "fixtureState={revision:1,part:record({stage:" + json.dumps(stage) + "})}; detail()")
    assert cycle(data["operations"][1]) == cycle(operation(readonly_detail(merged_cycle_api))) == (2, "operation")
    assert all(cycle(row) == (None, None) for row in data["operations"] if row["source"] == "internal")


def test_eu_process_stage_saved_blank_cycle_uses_actual_valid_group(merged_cycle_api):
    expression = """
    fixtureState={revision:1,part:record({stage:'hours'}),commands:[],receipts:{}};
    applyCommand('hours_confirm', {request_key:'eu-fixture-hours', input:{
      operations:fixtureState.part.operations.map(row=>({ref:row.ref,...(row.source==='external'
        ? {external_days:null} : {setup_hours:0,unit_hours:1.25})})),
      groups:[{ref:ref(400),total_days:3}]}});
    detail()
    """
    data = fixture_detail("process_stage_widgets_probe.cjs", "fixture", expression)
    assert data["workflow"]["ready"] is True
    assert cycle(data["operations"][1]) == cycle(operation(readonly_detail(merged_cycle_api))) == (None, "group")
    assert data["external_groups"][0]["total_days"] == 3

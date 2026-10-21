"""Old read consumers use common resource facts while preserving old aliases."""

import json
import subprocess
from pathlib import Path

import pytest

from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.facts.decision_metrics import metric_definitions
from core.services.workbench.run.candidate_comparison import read_candidate_comparison
from tests.workbench.dashboard_support import api
from tests.workbench.dashboard_support import dashboard_case as dashboard_case  # noqa: F401
from tests.workbench.node_runtime_support import node_runtime
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.test_run_decision_resource_api import WINDOW, reassigned_run
from tests.workbench.trial_support import change, create, service
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]


def shipped(data, program):
    result = subprocess.run([node_runtime(), str(ROOT / "tests/_support/gantt_current_runtime.cjs")],
                            input=json.dumps({"root": str(ROOT), "program": program, "data": data}),
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)["result"]


def trial_contract_and_capacity_panel(data):
    return shipped(data, r"""
const w = h.runtime, data = w.TrialContract.workspace(sourceData);
w.history = {state:null};
w.TrialViewState.useView = () => ({value:{...w.TrialViewState.defaults(data), result_tab:'capacity'},
  error:null, pending:false, change:() => true, reload() {}, reset() {}});
const display = structuredClone(data);
if (display.capacity.resources.length) {
  // Concurrent-span time and extra repeated time are distinct facts.
  display.capacity.resources[0].overlap_hours = 1.25;
  display.capacity.resources[0].window_metrics.overlap_hours = 2.5;
}
const tree = h.render(w.TrialResults.Results, {data:display, onSelect() {}}), text = h.text(tree);
if (data.capacity.resources.length) {
  for (const kind of ['machine','operator']) assert(text.includes(w.WorkbenchTerms.resource_kinds[kind]));
  const table = h.walk(tree).find(node => node.type === 'table' && node.props['aria-label'] === '资源占用');
  const rows = h.walk(table).find(node => node.type === 'tbody').children;
  display.capacity.resources.forEach((resource, index) => {
    const cells = rows[index].children;
    assert.equal(h.text(cells[4]), w.TrialControls.number(resource.window_metrics.overlap_hours));
    const facts = h.walk(cells[5]).find(node => node.type === 'dl');
    const values = h.walk(facts).filter(node => node.type === 'dd');
    assert.equal(h.text(values[1]), w.TrialControls.number(resource.overlap_hours));
    assert.equal(h.text(values[2]), w.TrialControls.number(resource.outside_available_hours));
  });
}
return {shipped_contract:true, capacity_panel:true};
""")


def test_old_candidate_comparison_fixed_cohort_and_archived_capacity(candidate_case, monkeypatch):
    case = candidate_case
    _, candidates = reassigned_run(case, monkeypatch=monkeypatch)
    rows = []
    for candidate in (candidates[0], candidates[-1]):
        data, _ = read_candidate_comparison(case.conn, RunCandidateReadScope(candidate, **WINDOW))
        common = data["resource_common"]
        assert common["source"] == "archived_resource_calendar"
        assert common["cohort_basis"] == "all_saved_candidates_and_admission_official"
        for kind in ("machine", "operator"):
            value = common["after"][kind]
            assert value["resource_count"] == 2 and value["used_resource_count"] == 1
            assert value["available_hours"] == 16 and value["occupied_hours"] == 0.75
            assert value["balance_cv"] == pytest.approx(1)
        assert len(data["resources"]) == 4
        assert all(row["before"]["window_metrics"]["occupied_hours"] is None for row in data["resources"])
        definitions = {row["key"]: row for row in metric_definitions()}
        for entry in data["tradeoffs"]["all_differences"]:
            assert entry["metric_version"] == definitions[entry["metric_key"]]["metric_version"]
            if entry["source"] == "archived_resource_calendar":
                assert entry["metric_version"] == common["metric_version"]
        assert data["summary"]["before"]["changeovers"]["reason"] == "比较对象缺少保存安排，工种切换次数未知。"
        shipped(data, r"""
const w = h.runtime, d = sourceData;
const payload = {ok:true, schema_version:1, data:d, meta:{request_ref:'a'.repeat(32), source:'production',
  time_basis:'factory_local', snapshot_ref:'b'.repeat(32), as_of:'2026-09-10T12:00:00'}, warnings:[]};
w.DashboardCandidateComparisonAPI.validate(payload, {candidate:d.candidate, batch_ref:d.batch_ref},
  {baseline:d.baseline, generation:d.generation, time_scope:d.time_scope});
const text = h.text(h.render(w.DashboardCandidatePanels.Metrics, {data:d}));
assert(text.includes(w.WorkbenchTerms.resource_kinds.machine) && text.includes(w.WorkbenchTerms.resource_kinds.operator));
assert(text.includes('比较对象缺少保存安排，工种切换次数未知。'));
assert(!text.includes('arrangements_unavailable'));
const tree = h.render(w.DashboardCandidatePanels.Tradeoffs, {data:d});
const rows = h.walk(tree).filter(node => node.props['data-comparison-tradeoff']);
assert.equal(rows.length, d.tradeoffs.all_differences.length);
for (const item of d.tradeoffs.all_differences) {
  const row = rows.find(node => node.props['data-comparison-tradeoff'] === item.metric_key);
  assert(row && h.text(row).includes(item.text), 'The old dashboard consumes the shared explanation verbatim');
}
assert(!text.includes('推荐方案'), 'The old dashboard compares the explicitly selected candidate');
const missing = structuredClone(payload);
delete missing.data.tradeoffs.all_differences[0].value;
assert.throws(() => w.DashboardCandidateComparisonAPI.validate(missing,
  {candidate:d.candidate, batch_ref:d.batch_ref}, {baseline:d.baseline, generation:d.generation, time_scope:d.time_scope}));
const resources = d.tradeoffs.all_differences.filter(item => item.source === 'archived_resource_calendar');
assert(resources.length && resources.every(item => item.metric_version === d.resource_common.metric_version));
const wrongVersion = structuredClone(payload), key = resources[0].metric_key;
for (const group of ['all_differences','benefits','costs']) {
  for (const item of wrongVersion.data.tradeoffs[group]) if (item.metric_key === key) item.metric_version = 'decision-preparation-v4';
}
assert.throws(() => w.DashboardCandidateComparisonAPI.validate(wrongVersion,
  {candidate:d.candidate, batch_ref:d.batch_ref}, {baseline:d.baseline, generation:d.generation, time_scope:d.time_scope}));
return {shipped_contract:true, fixed_cohort:true};
""")
        rows.append(data)
    assert rows[0]["resource_common"]["cohort"] == rows[1]["resource_common"]["cohort"]
    case.conn.execute("UPDATE WorkbenchCalendarDefaults SET periods_json='[]'")
    case.conn.execute("UPDATE Machines SET name='Current renamed machine'")
    case.conn.commit()
    reread, _ = read_candidate_comparison(case.conn, RunCandidateReadScope(candidates[0], **WINDOW))
    assert reread["resources"] == rows[0]["resources"]
    assert reread["resource_common"] == rows[0]["resource_common"]


def test_trial_capacity_uses_creation_archive_after_live_calendar_changes(trial_case):
    case = trial_case
    draft = create(case)
    baseline = draft["capacity"]
    assert baseline["source"] == "archived_resource_calendar"
    assert all(row["window_metrics"]["available_hours"] == 3 for row in baseline["resources"])
    case.conn.execute("UPDATE WorkbenchCalendarDefaults SET periods_json='[]'")
    case.conn.commit()
    reread = service(case.conn).get(draft["draft_ref"])
    assert reread["capacity"] == baseline
    trial_contract_and_capacity_panel(reread)
    # Validation continues to consult the edited current calendar.
    assert reread["validation"]["constraints_status"] == "blocked"


def test_trial_new_permanent_resource_ref_stays_unknown_in_original_archive(trial_case):
    case = trial_case
    draft = create(case)
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M4','New lathe','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O4','New operator')")
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O4','M4')")
    case.conn.commit()
    refreshed = service(case.conn).get(draft["draft_ref"])
    changed = change(case, refreshed, machine="M4", operator="O4")["data"]
    for kind, key in (("machine", "M4"), ("operator", "O4")):
        resource = next(row for row in changed["capacity"]["resources"] if row["resource_ref"] == case.ref(kind, key))
        assert resource["window_metrics"]["available_hours"] is None
        assert resource["window_metrics"]["occupied_hours"] is None
        assert resource["window_metrics"]["span_occupied_hours"] == 3
        assert resource["window_metrics"]["issues"][0]["code"] == "resource_missing"
    assert {item["code"] for item in changed["validation"]["issues"]} == {"trial_facts_changed"}
    saved = service(case.conn).save(draft["draft_ref"], {"name": "New live assignment"},
                                   changed["write_context"]["write_token"], "legacy-resource-save-01")["data"]
    assert service(case.conn).scenario(saved["scenario_ref"])["capacity"] == saved["capacity"]
    trial_contract_and_capacity_panel(saved)


def test_current_dashboard_two_kinds_share_fact_contract_without_rederiving_pressure(dashboard_case, monkeypatch):
    client = api(dashboard_case, monkeypatch)
    response = client.get('/api/workbench/v1/dashboard/analysis', query_string={'section': 'pressure'})
    assert response.status_code == 200
    document = response.get_json()
    data = document["data"]
    assert {row["kind"] for row in data["resources"]} == {"machine", "operator"}
    assert data["resource_common"]["source"] == "current_transaction_snapshot"
    program = r"""
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const w = {}, context = vm.createContext({window:w, AbortController, URLSearchParams, setTimeout, clearTimeout});
for (const file of ['DashboardContract.js', 'RunCandidateAPI.js', 'ResourceProjectionContract.js', 'DashboardAnalysisAPI.js'])
  vm.runInContext(fs.readFileSync(path.join(process.cwd(), 'frontend/workbench/app', file), 'utf8'), context);
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
w.DashboardAnalysisAPI.validate(payload);
// A missing canonical fact is a transport error, not a computed default.
delete payload.data.resources[0].window_metrics.summed_load_hours;
let rejected = false; try { w.DashboardAnalysisAPI.validate(payload); } catch (_) { rejected = true; }
if (!rejected) throw new Error('missing canonical resource field was accepted');
process.stdout.write('common-contract-ok');
"""
    result = subprocess.run([node_runtime(), '-e', program], input=json.dumps(document), text=True,
                            capture_output=True, cwd=ROOT, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("base", ["candidate", "official"])
def test_trial_proven_point_remains_readable_without_resource_occupancy(trial_case, base):
    from tests.workbench.ea_zero_duration_support import adopt, point_candidate

    case = trial_case
    candidate = point_candidate(case)
    origin = {"candidate_ref": candidate} if base == "candidate" else {"plan_ref": adopt(case, candidate)["plan_ref"]}
    draft = create(case, {"base": origin})
    point, = draft["tasks"]
    assert point["event_kind"] == "point" and point["occupies_resources"] is False
    assert draft["capacity"]["resources"] == []
    assert draft["capacity"]["resource_common"]["machine"]["occupied_hours"] == 0
    assert service(case.conn).get(draft["draft_ref"])["capacity"] == draft["capacity"]
    trial_contract_and_capacity_panel(draft)


def test_trial_legacy_concurrent_span_and_common_excess_load_remain_distinct(trial_case):
    from tests.workbench.trial_support import official

    case = trial_case
    second, third = case.operation(seq=2), case.operation(seq=3)
    case.conn.commit()
    draft = create(case, official(case, ids=[case.op_id, second, third]))
    assert len(draft["capacity"]["resources"]) == 2
    for resource in draft["capacity"]["resources"]:
        value = resource["window_metrics"]
        assert resource["arranged_hours"] == value["summed_load_hours"] == 9
        assert resource["occupied_hours"] == value["occupied_hours"] == 3
        assert resource["overlap_hours"] == 3
        assert value["overlap_hours"] == value["span_overlap_hours"] == 6
        assert value["utilization_ratio"] == 1 and value["demand_ratio"] == 3
        assert resource["segments"] == [{"start": "2026-09-09T08:00:00", "end": "2026-09-09T11:00:00", "concurrent_operations": 3}]

"""Compact analysis keeps execution facts and reuses its complete task scope."""

import copy
import json
import subprocess
from pathlib import Path

import pytest

from core.services.workbench.dashboard.execution import actual
from core.services.workbench.dashboard.service import WorkbenchDashboardService
from tests.workbench.dashboard_support import NOW, api
from tests.workbench.dashboard_support import dashboard_case as dashboard_case  # noqa: F401
from tests.workbench.node_runtime_support import node_runtime

ROOT = Path(__file__).resolve().parents[2]
BASE = "/api/workbench/v1/dashboard"
TASK_FIELDS = {"kind", "plan_ref", "operation_ref", "batch_id", "planned_start", "planned_end"}


def source_and_analysis(case):
    reader = WorkbenchDashboardService(case.conn, clock=lambda: NOW)
    with reader.read_snapshot():
        sources = reader.load()
    reader.project(sources)
    original = copy.deepcopy(actual(sources.facts)[0][0]["source"])
    compact = reader.analysis(sources)
    assert actual(sources.facts)[0][0]["source"] == original
    return original, compact


@pytest.mark.parametrize("quantity,hours", [(2, 1.5), (None, None)])
def test_analysis_preserves_actual_values_unknowns_and_evidence_references(dashboard_case, quantity, hours):
    case = dashboard_case
    case.report(quantity=quantity, effective_processing_hours=hours)
    original, compact = source_and_analysis(case)
    row = compact["execution"][0]
    task = compact["tasks"][0]
    assert set(row) == {"source", "batch_ref"}
    assert row["source"] == {key: value for key, value in original.items() if key not in TASK_FIELDS}
    assert row["source"]["task_ref"] == task["task_ref"] and row["batch_ref"] == task["batch_ref"]
    assert task["plan_ref"] == original["plan_ref"]
    assert task["operation_ref"] == original["operation_ref"]
    assert (task["start"], task["end"]) == (original["planned_start"], original["planned_end"])
    assert row["source"]["report_refs"] and row["source"]["legacy_fact_refs"] == original["legacy_fact_refs"]
    if quantity is None:
        assert row["source"]["data_quality"] == "incomplete"
        assert row["source"]["data_gaps"]
        assert row["source"]["hours"]["effective_processing_hours"] is None
        assert row["source"]["hours"]["overrun"] is None
        assert row["source"]["completion_basis"] is None
    else:
        assert row["source"]["execution_state"] == "complete"
        assert row["source"]["confirmed_finish"] == "2026-09-09T10:20:00"
        assert row["source"]["hours"]["effective_processing_hours"] == 1.5
        assert row["source"]["hours"]["overrun"] is True
        assert row["source"]["finish_deviation_minutes"] == 20


def test_http_analysis_dedup_does_not_reduce_list_or_detail_evidence(dashboard_case, monkeypatch):
    case = dashboard_case
    case.report()
    client = api(case, monkeypatch)
    listing = client.get(BASE)
    assert listing.status_code == 200
    document = listing.get_json()
    item = next(row for row in document["data"]["items"] if row["category"] == "actual")
    assert TASK_FIELDS <= set(item["source"])
    compact = document["data"]["analysis"]["execution"][0]["source"]
    assert not TASK_FIELDS.intersection(compact)
    detail = client.get(BASE + "/items/" + item["item_ref"], query_string={"snapshot_ref": document["meta"]["snapshot_ref"]})
    assert detail.status_code == 200
    assert detail.get_json()["data"]["item"]["source"] == item["source"]
    standalone = client.get(BASE + "/analysis")
    assert standalone.status_code == 200
    assert standalone.get_json()["data"]["execution"] == document["data"]["analysis"]["execution"]


def test_shipped_react_analysis_uses_task_identity_for_both_navigation_handlers(dashboard_case, monkeypatch):
    client = api(dashboard_case, monkeypatch)
    document = client.get(BASE + "/analysis").get_json()
    program = r"""
const w = h.runtime, data = w.DashboardAnalysisAPI.validate(sourceData);
const tasks = new Map(data.tasks.map(task => [task.task_ref, task]));
const calls = [];
function check(value) {
  const tree = h.render(w.DashboardAnalysisPanels.Actual, {data: value, navigate: entry => calls.push(entry)});
  const buttons = h.walk(tree).filter(node => node.type === 'button');
  assert.strictEqual(buttons.length, data.execution.length * 2);
  data.execution.forEach((row, index) => {
    const task = tasks.get(row.source.task_ref);
    assert(h.text(tree).includes(task.batch_id + ' · ' + task.process_label));
    buttons[index * 2].props.onClick({currentTarget: {}, preventDefault() {}});
    buttons[index * 2 + 1].props.onClick({currentTarget: {}, preventDefault() {}});
    for (const [entry, view] of [[calls[calls.length - 2], 'field'], [calls[calls.length - 1], 'fieldgantt']]) {
      assert.strictEqual(entry.view, view); assert.strictEqual(entry.enabled, true);
      assert.strictEqual(entry.context.plan_ref, data.plan.plan_ref);
      assert.strictEqual(entry.context.task_ref, task.task_ref);
      assert.strictEqual(entry.context.operation_ref, task.operation_ref);
    }
  });
}
check(data);
// Old, richer analysis DTOs use the same authoritative task mapping.
const rich = {...data, execution: data.execution.map(row => ({...row, subject: 'legacy label',
  source: {...row.source, plan_ref: data.plan.plan_ref, operation_ref: tasks.get(row.source.task_ref).operation_ref}}))};
check(rich);
return {navigation_clicks: calls.length, shipped_react: true};
"""
    result = subprocess.run([node_runtime(), str(ROOT / "tests/_support/gantt_current_runtime.cjs")],
        input=json.dumps({"root": str(ROOT), "program": program, "data": document}),
        text=True, encoding="utf-8", capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["result"]["navigation_clicks"] == 4

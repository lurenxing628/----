"""Current strict DTO, cross-page identities and pinned CSV/XLSX exports."""

from copy import deepcopy

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench import plan_adoption_baseline_values as values
from tests.workbench.plan_read_support import assert_error, make_api
from tests.workbench.test_plan_adoption_baseline_support import adopt_candidate, read, two_versions
from tests.workbench.test_plan_adoption_baseline_support import trial_case as trial_case  # noqa: F401
from tests.workbench.test_plan_export_api import read_rows
from tests.workbench.test_plan_transport import catalog_fixture, run_probe, workspace_fixture


@pytest.mark.parametrize("source", ["candidate", "trial"])
def test_cross_page_catalog_workspace_and_strict_dto(trial_case, tmp_path, source):
    first, second = two_versions(trial_case, source)
    api = make_api(trial_case.path)
    latest = catalog_fixture(api, "new official", size=1)
    page = latest["payload"]
    original = catalog_fixture(api, "original official", size=1, cursor=page["data"]["page"]["next_cursor"],
                               snapshot_ref=page["meta"]["snapshot_ref"])
    assert latest["payload"]["data"]["plans"][0]["plan_ref"] == second["plan_ref"]
    assert original["payload"]["data"]["plans"][0]["plan_ref"] == first["plan_ref"]
    selected = workspace_fixture(api, source + " adopted", second["plan_ref"])
    baseline = selected["payload"]["data"]["projections"]["baseline"]
    assert baseline["state"] == "available" and baseline["baseline_plan"]["plan_ref"] == first["plan_ref"]
    initial = workspace_fixture(api, "first adoption", first["plan_ref"])
    fixtures = [latest, original, selected, initial]
    for field, value in (("basis", "scenario_base"), ("basis", "invented"), ("compared_fields", ["supplier_ref"])):
        bad = deepcopy(selected)
        bad.update(name="reject " + field + str(value), contract_error=True)
        bad["payload"]["data"]["projections"]["baseline"][field] = value
        fixtures.append(bad)
    bad = deepcopy(selected)
    bad.update(name="reject current-official baseline", contract_error=True)
    bad["payload"]["data"]["projections"]["baseline"]["baseline_plan"]["is_current_official"] = True
    fixtures.append(bad)
    for code in values.REASONS:
        unavailable = deepcopy(initial)
        unavailable["name"] = code
        unavailable["payload"]["data"]["projections"]["baseline"]["reason_code"] = code
        fixtures.append(unavailable)
    assert run_probe(tmp_path, fixtures)["checks"] == len(fixtures)


@pytest.mark.parametrize("source", ["candidate", "trial"])
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_export_matches_selected_complete_tasks_and_rejects_changed_baseline(trial_case, source, fmt):
    first, second = two_versions(trial_case, source)
    api = make_api(trial_case.path)
    ref = second["plan_ref"]
    whole = api.read("/" + ref + "/workspace")
    item = whole["data"]["projections"]["baseline"]["items"][0]
    scopes = [{}, {"range_start": item["after"]["start"], "range_end": item["after"]["end"]}]
    if source == "trial":
        scopes.append({"range_start": item["before"]["start"], "range_end": item["before"]["end"]})
    before = api.state()
    for scope in scopes:
        workspace = api.read("/" + ref + "/workspace", **scope)
        snapshot = workspace["meta"]["snapshot_ref"]
        response = api.get("/" + ref + "/export", format=fmt, snapshot_ref=snapshot, **scope)
        rows = read_rows(response, fmt)
        assert [row[11] for row in rows[1:]] == [task["task_ref"] for task in workspace["data"]["tasks"]]
        assert [row[22:24] for row in rows[1:]] == [type(rows[0])((task["start"], task["end"])) for task in workspace["data"]["tasks"]]
        assert response.headers["X-Workbench-Plan-Ref"] == ref
        assert response.headers["X-Workbench-Snapshot-Ref"] == snapshot
    assert api.state() == before
    trial_case.conn.execute("UPDATE Schedule SET created_at='original raw drift' WHERE version=?", (first["version"],))
    trial_case.conn.commit()
    assert_error(api.get("/" + ref + "/export", format=fmt, snapshot_ref=whole["meta"]["snapshot_ref"]), "snapshot_stale")
    fresh = api.read("/" + ref + "/workspace")
    assert fresh["data"]["projections"]["baseline"]["reason_code"] == "adoption_baseline_drift"


def test_complete_multitask_identity_checked_before_narrow_scope(trial_case):
    case = trial_case
    for seq in range(2, 102):
        case.operation(seq=seq, unit_hours=0.01)
    case.conn.commit()
    _, second = two_versions(case, "candidate")
    full, facts = read(case, second)
    assert full["state"] == "available", (full, facts.get("evidence_gap"))
    assert len(full["items"]) == 101
    last = max((item["after"] for item in full["items"]), key=lambda row: row["end"])
    data, _ = read(case, second, last["start"], last["end"])
    assert len(data["items"]) == 1
    assert data["items"][0]["after"] == last
    case.conn.execute("UPDATE Schedule SET created_at='offscreen drift' WHERE version=1 AND op_id=?", (case.op_id,))
    case.conn.commit()
    assert read(case, second, last["start"], last["end"])[0]["reason_code"] == "adoption_baseline_drift"


def test_whole_read_capacity_is_not_bypassed_by_empty_scope(trial_case, monkeypatch):
    first = adopt_candidate(trial_case)
    second = adopt_candidate(trial_case, "second")
    assert read(trial_case, second)[0]["baseline_plan"]["plan_ref"] == first["plan_ref"]
    monkeypatch.setattr(values, "MAX_PLAN_TASKS", 0)
    with pytest.raises(WorkbenchCommandRejected) as error:
        read(trial_case, second, "2026-10-01T00:00:00", "2026-10-02T00:00:00")
    assert error.value.code == "query_too_large" and error.value.status == 413

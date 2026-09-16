"""Inherited trial origins and constraint presentation never grant adoption."""

import pytest

from core.models.workbench_trial import issue, validation
from tests.workbench.trial_adoption_support import saved_scenario
from tests.workbench.trial_adoption_support import service as adoption_service
from tests.workbench.trial_support import api, candidate, create, official, service, snapshot
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401


@pytest.mark.parametrize("kind", ["official", "candidate"])
def test_preview_returns_exact_inherited_source_identity_without_writes(trial_case, kind):
    case = trial_case
    intent = official(case) if kind == "official" else candidate(case)
    before = snapshot(case.conn)
    client = api(case)
    response = client.post("/api/workbench/v1/trial/drafts/preview", json=intent)
    assert response.status_code == 200
    preview = response.get_json()["data"]
    key, ref = next(iter(intent["base"].items()))
    assert preview["base_identity"][key] == ref
    assert preview["base_identity"]["display_name"]
    assert preview["task_count"] == 1
    assert snapshot(case.conn) == before
    draft = create(case, intent)
    assert preview["base_identity"] == draft["base_identity"]
    assert all(row["code"] != "scenario_adoption_not_connected" for row in draft["validation"]["issues"])
    assert draft["validation"]["can_adopt"] is False


def test_real_constraints_survive_without_synthetic_capability_conflict():
    clean = validation([])
    assert clean["status"] == clean["constraints_status"] == "valid"
    assert clean["issues"] == [] and clean["can_adopt"] is False
    assert clean["adoption"]["blocked_reasons"][0]["code"] == "scenario_adoption_preview_required"
    warning = issue("ready_unknown", "齐套日期未知", severity="warning")
    blocker = issue("resource_overlap", "设备时段冲突")
    assert validation([warning])["status"] == "warning"
    checked = validation([warning, blocker])
    assert checked["status"] == checked["constraints_status"] == "blocked"
    assert checked["issues"] == [warning, blocker]
    assert checked["can_adopt"] is False


def test_partial_candidate_trial_still_cannot_replace_full_official_scope(trial_case):
    case = trial_case
    case.batch("B2")
    other = case.operation("B2", machine_id="M3", operator_id="O3")
    case.plan(1, [other], start="2026-09-10T08:00:00", end="2026-09-10T11:00:00")
    source = candidate(case)  # Candidate contains B1, while the official plan still contains B2.
    saved = saved_scenario(case, source, changed=False)
    before = snapshot(case.conn)
    result = adoption_service(case.conn).preview(saved["scenario_ref"])
    assert result["validation"]["can_adopt"] is False
    assert result["write_context"]["write_token"] is None
    reason = result["validation"]["issues"][0]
    assert reason["code"] == "official_scope_not_covered", result
    assert "没有覆盖当前正式计划的全部工序" in reason["message"]
    assert "功能尚未开通" not in reason["message"]
    assert snapshot(case.conn) == before

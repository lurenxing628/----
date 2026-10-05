"""Current strict DTO, cross-page identities and pinned CSV/XLSX exports."""

from copy import deepcopy

import pytest

from core.services.workbench.plan import adoption_baseline_values as values
from tests.workbench.plan_adoption_baseline_support import trial_case as trial_case  # noqa: F401
from tests.workbench.plan_adoption_baseline_support import two_versions
from tests.workbench.plan_read_support import make_api
from tests.workbench.plan_transport_support import catalog_fixture, run_probe, workspace_fixture


@pytest.mark.parametrize("source", ["trial"])
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

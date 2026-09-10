"""Real GET routes: strict query scope, paging and snapshot refresh."""

import pytest

from tests.workbench.trial_adoption_history_support import advance, api, seeded
from tests.workbench.trial_adoption_history_support import trial_case as trial_case  # noqa: F401
from tests.workbench.trial_support import snapshot


def url(saved):
    return "/api/workbench/v1/trial/scenarios/" + saved["scenario_ref"] + "/adoption-history"


def test_actual_sqlite_read_only_snapshot_and_filters(trial_case):
    saved, _ = seeded(trial_case)
    client = api(trial_case)
    before = snapshot(trial_case.conn)
    first = client.get(url(saved))
    assert first.status_code == 200, first.json
    assert first.headers["Cache-Control"] == "no-store"
    token = first.json["meta"]["snapshot_ref"]
    assert client.get(url(saved), query_string={"snapshot_ref": token}).json["data"] == first.json["data"]
    assert client.get(url(saved), query_string={"snapshot_ref": token, "status": "current"}).status_code == 409
    assert snapshot(trial_case.conn) == before
    advance(trial_case)
    stale = client.get(url(saved), query_string={"snapshot_ref": token})
    assert stale.status_code == 409 and stale.json["error"]["code"] == "snapshot_stale"
    refreshed = client.get(url(saved), query_string={"status": "historical"})
    assert refreshed.status_code == 200 and refreshed.json["data"]["page"]["total"] == 1
    assert client.get(url(saved), query_string={"status": "current"}).json["data"]["items"] == []


@pytest.mark.parametrize("query", ["page=0", "page=2", "size=51", "page=1.0", "status=latest", "status=all&status=current", "plan_ref=latest", "size=10&size=10"])
def test_reject_unknown_duplicate_unbounded_and_unpinned_page(trial_case, query):
    saved, _ = seeded(trial_case)
    response = api(trial_case).get(url(saved) + "?" + query)
    assert response.status_code == 400, response.json


def test_restart_requires_explicit_snapshot_refresh(trial_case):
    saved, _ = seeded(trial_case)
    client = api(trial_case)
    first = client.get(url(saved)).json
    trial_case.app.extensions.pop("aps_public_opaque_tokens", None)
    assert client.get(url(saved), query_string={"snapshot_ref": first["meta"]["snapshot_ref"]}).status_code == 409
    assert client.get(url(saved)).json["data"] == first["data"]


def test_fixed_snapshot_covers_every_numbered_page(trial_case):
    from tests.workbench.trial_adoption_history_support import raw_receipt
    saved, _ = seeded(trial_case)
    for index in range(3):
        raw_receipt(trial_case.conn, saved, key=f"db-api-page-fault-{index:04d}",
                    plan={"plan_ref": f"{index + 1:048x}", "version": 30 + index})
    client = api(trial_case)
    first = client.get(url(saved), query_string={"size": 2}).json
    query = {"page": 2, "size": 2, "snapshot_ref": first["meta"]["snapshot_ref"]}
    second = client.get(url(saved), query_string=query)
    assert second.status_code == 200, second.json
    assert second.json["meta"]["as_of"] == first["meta"]["as_of"]
    assert len({row["receipt_ref"] for row in first["data"]["items"] + second.json["data"]["items"]}) == 4
    advance(trial_case)
    stale = client.get(url(saved), query_string=query)
    assert stale.status_code == 409 and stale.json["error"]["code"] == "snapshot_stale"

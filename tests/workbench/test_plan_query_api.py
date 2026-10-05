"""Read-chain contracts with real persisted identities and a new DB connection per request."""


from tests.workbench.plan_read_support import NIGHT_END, NIGHT_START, assert_error, plan_read_api  # noqa: F401


def test_workspace_real_night_interval_and_real_full_projections(plan_api):
    ref = plan_api.ref()
    result = plan_api.read("/" + ref + "/workspace")
    data = result["data"]
    assert data["plan_span"] == data["task_span"] == {"start": NIGHT_START, "end": NIGHT_END}
    assert data["time_scope"]["range_start"] == NIGHT_START and data["time_scope"]["range_end"] == NIGHT_END
    assert data["task_count"] == len(data["tasks"]) == 1 and data["tasks_complete"] is True
    assert data["tasks"][0]["start"] == NIGHT_START and data["tasks"][0]["end"] == NIGHT_END
    assert data["projections"]["baseline"]["state"] == "unavailable"
    assert data["projections"]["baseline"]["reason_code"] == "not_recorded"
    assert data["projections"]["calendar"]["state"] == "available"
    assert data["projections"]["occupancy"]["state"] == "available"
    assert data["projections"]["delivery_risks"]["state"] == "unavailable"
    assert set(data["projections"]) == {"baseline", "calendar", "occupancy", "delivery_risks", "process_order"}
    assert data["projections"]["process_order"]["state"] == "unavailable"
    detail = plan_api.read("/" + ref, snapshot_ref=result["meta"]["snapshot_ref"])
    assert detail["data"] == data and detail["meta"]["snapshot_ref"] == result["meta"]["snapshot_ref"]


def test_workspace_snapshot_binds_plan_range_and_related_resource_facts(plan_api):
    ref = plan_api.ref()
    first = plan_api.read("/" + ref + "/workspace")
    token = first["meta"]["snapshot_ref"]
    assert plan_api.read("/" + ref + "/workspace", snapshot_ref=token)["meta"]["as_of"] == first["meta"]["as_of"]
    assert_error(plan_api.get("/" + plan_api.ref(role="baseline_best") + "/workspace", snapshot_ref=token), "snapshot_stale")
    assert_error(plan_api.get("/" + ref + "/workspace", snapshot_ref=token,
                             range_start=NIGHT_START, range_end=NIGHT_END), "snapshot_stale")
    with plan_api.db() as conn:
        conn.execute("UPDATE Machines SET remark='New maintenance fact' WHERE machine_id='PRIVATE-M1'")
    assert_error(plan_api.get("/" + ref + "/workspace", snapshot_ref=token), "snapshot_stale")

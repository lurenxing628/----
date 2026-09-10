"""Read-chain contracts with real persisted identities and a new DB connection per request."""

import json
from types import SimpleNamespace

import pytest

import web.public_token_registry as tokens
from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.services.scheduler import workbench_plan_catalog
from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository
from tests.workbench.plan_catalog_support import history
from tests.workbench.plan_read_support import BASE, NIGHT_END, NIGHT_START, assert_error, make_api, plan_read_api


def test_directory_has_exact_public_identity_and_seeks_versions(plan_api, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Public read must not scan full history/catalog")

    monkeypatch.setattr(workbench_plan_catalog, "build_plan_catalog", forbidden)
    monkeypatch.setattr(SchedulePlanQueryRepository, "list_history_identity_rows", forbidden)
    first = plan_api.read(size=1)
    assert len(first["data"]["plans"]) == 3
    official, alias, candidate = first["data"]["plans"]
    assert set(official) == {"plan_ref", "version", "kind", "is_current_official", "display_name",
                             "completeness", "capabilities", "blocked_reasons"}
    assert official["kind"] == "official" and official["is_current_official"] is True
    assert official["capabilities"] == {"view": True, "export": True, "edit_draft": False, "adopt": False, "report_actual": False}
    assert alias["kind"] == candidate["kind"] == "candidate"
    assert not alias["is_current_official"] and alias["plan_ref"] != official["plan_ref"]
    cursor = first["data"]["page"]["next_cursor"]
    second = plan_api.read(size=1, cursor=cursor)
    assert second["meta"]["snapshot_ref"] == first["meta"]["snapshot_ref"]
    assert [row["version"] for row in second["data"]["plans"]] == [2]
    last = plan_api.read(size=1, cursor=second["data"]["page"]["next_cursor"])
    assert [row["version"] for row in last["data"]["plans"]] == [1]
    assert last["data"]["page"]["has_more"] is False and last["data"]["page"]["next_cursor"] is None
    assert not any("OFFSET" in sql.upper() for sql in plan_api.statements)


@pytest.mark.parametrize("status", ["partial", "failed"])
def test_latest_incomplete_never_falls_back_to_older_success(plan_api, status):
    with plan_api.db() as conn:
        history(conn, 4, status)
    first = plan_api.read(size=1)
    latest = first["data"]["plans"][0]
    assert latest["version"] == 4 and not latest["capabilities"]["view"]
    older = plan_api.read(size=1, cursor=first["data"]["page"]["next_cursor"])
    assert all(not row["is_current_official"] for row in older["data"]["plans"])
    assert_error(plan_api.get("/" + latest["plan_ref"] + "/workspace"), "plan_unavailable")


@pytest.mark.parametrize("mutation", [
    "UPDATE Schedule SET end_time='2026-09-10 07:00:00' WHERE version=3",
    "UPDATE ScheduleHistory SET result_summary='{\"changed\":true}' WHERE version=1",
    "UPDATE ScheduleCandidate SET candidate_label='Changed label' WHERE version=3",
    "UPDATE ScheduleAdjustmentScenario SET status='expired' WHERE status='active'",
])
def test_cursor_rejects_changed_plan_facts_including_offpage(plan_api, mutation):
    first = plan_api.read(size=1)
    with plan_api.db() as conn:
        conn.execute(mutation)
    assert_error(plan_api.get(size=1, cursor=first["data"]["page"]["next_cursor"]), "snapshot_stale")


@pytest.mark.parametrize("changed", [{"size": 2}, {"collection": "scenario"}, {"snapshot_ref": "missing"}])
def test_cursor_cannot_change_collection_size_or_snapshot(plan_api, changed):
    first = plan_api.read(size=1)
    query = {"size": 1, "cursor": first["data"]["page"]["next_cursor"], **changed}
    assert_error(plan_api.get(**query), "snapshot_stale")


def test_cursor_is_server_held_short_lived_and_restart_invalid(plan_api, monkeypatch):
    now = [1000000.0]
    monkeypatch.setattr(tokens, "time", SimpleNamespace(time=lambda: now[0]))
    first = plan_api.read(size=1)
    cursor = first["data"]["page"]["next_cursor"]
    assert len(cursor) == 32 and not cursor.isdigit()
    with plan_api.app.app_context():
        value = tokens.resolve_public_token("workbench-plan-catalog-cursor-v1", cursor, message="test", field="cursor")
        assert json.loads(value)["seek"] == 3
    assert_error(make_api(plan_api.path).get(size=1, cursor=cursor), "snapshot_stale")
    now[0] += 901
    assert_error(plan_api.get(size=1, cursor=cursor), "snapshot_stale")


def test_scenario_catalog_pages_keep_inactive_objects_unavailable(plan_api):
    first = plan_api.read(collection="scenario", size=1)
    active = first["data"]["plans"][0]
    assert active["kind"] == "scenario" and active["capabilities"]["view"]
    assert not active["is_current_official"]
    cursor = first["data"]["page"]["next_cursor"]
    for _ in range(2):
        page = plan_api.read(collection="scenario", size=1, cursor=cursor)
        entry = page["data"]["plans"][0]
        assert entry["capabilities"]["view"] is False
        assert entry["blocked_reasons"][0]["code"] == "scenario_not_active"
        assert_error(plan_api.get("/" + entry["plan_ref"] + "/workspace"), "plan_unavailable")
        cursor = page["data"]["page"]["next_cursor"]
    assert cursor is None


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


def test_time_scope_uses_strict_overlap_and_never_clips_real_task_span(plan_api):
    path = "/" + plan_api.ref() + "/workspace"
    query = {"range_start": "2026-09-10T00:00:00", "range_end": "2026-09-10T01:00:00"}
    data = plan_api.read(path, **query)["data"]
    assert data["task_span"] == {"start": NIGHT_START, "end": NIGHT_END}
    assert data["time_scope"]["range_start"] == query["range_start"]
    empty = plan_api.read(path, range_start=NIGHT_END, range_end="2026-09-10T08:00:00")["data"]
    assert empty["tasks"] == [] and empty["task_count"] == 0 and empty["task_span"] is None
    assert empty["plan_span"] == data["plan_span"]


@pytest.mark.parametrize("query", [
    {"range_start": NIGHT_START}, {"range_start": NIGHT_END, "range_end": NIGHT_START},
    {"range_start": "2026-02-30T12:00:00", "range_end": NIGHT_END},
    {"range_start": "2026-09-09T22:30:00Z", "range_end": NIGHT_END},
    {"range_start": "2026-09-09", "range_end": NIGHT_END},
    {"baseline_ref": "unsupported"}, {"resource_ref": "unsupported"}, {"scenario_id": "PRIVATE-ACTIVE"},
])
def test_workspace_never_ignores_invalid_or_unsupported_scope(plan_api, query):
    assert_error(plan_api.get("/" + plan_api.ref() + "/workspace", **query), "invalid_input", 400)


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


def test_query_only_zero_database_changes_and_persisted_refs_survive_restart(plan_api):
    before = plan_api.state()
    ref = plan_api.ref()
    first = plan_api.read("/" + ref + "/workspace")
    plan_api.read()
    plan_api.read(collection="scenario")
    assert plan_api.state() == before
    unexpected = [sql for sql in plan_api.statements if not sql.startswith("-- PRAGMA ")
                  and sql.lstrip().split()[0].upper() not in {"SELECT", "WITH", "BEGIN", "COMMIT"}]
    assert unexpected == []
    restarted = make_api(plan_api.path)
    second = restarted.read("/" + ref + "/workspace")
    assert second["data"]["tasks"] == first["data"]["tasks"]
    assert_error(restarted.get("/" + ref + "/workspace", snapshot_ref=first["meta"]["snapshot_ref"]), "snapshot_stale")


def test_missing_plan_rejects_instead_of_resolving_latest(plan_api):
    assert_error(plan_api.get("/" + "a" * 48 + "/workspace"), "entity_not_found", 404)
    assert_error(plan_api.get("/3/workspace"), "entity_not_found", 404)
    ref = plan_api.ref(1)
    original = plan_api.read("/" + ref + "/workspace")
    with plan_api.db() as conn:
        conn.execute("DELETE FROM ScheduleHistory WHERE version=1")
    assert_error(plan_api.get("/" + ref + "/workspace"), "plan_binding_invalid")
    with plan_api.db() as conn:
        history(conn, 1)
    assert plan_api.ref(1) == ref
    assert plan_api.read("/" + ref + "/workspace")["data"] == original["data"]
    assert_error(plan_api.get("/" + ref + "/workspace", snapshot_ref=original["meta"]["snapshot_ref"]), "snapshot_stale")


def test_empty_database_and_missing_identity_schema_are_distinct(schema_conn, tmp_path):
    path = tmp_path / "empty-plans.db"
    from tests.workbench.plan_read_support import connect

    target = connect(path)
    schema_conn.backup(target)
    install_plan_identity(target)
    target.commit()
    target.close()
    api = make_api(path)
    assert api.read()["data"]["plans"] == []
    assert api.read(collection="scenario")["data"]["plans"] == []
    with api.db() as conn:
        conn.execute("DROP TABLE WorkbenchPlanIdentityClock")
    assert_error(api.get(), "storage_failure", 500)


@pytest.mark.parametrize("query", [{"size": "0"}, {"size": "51"}, {"size": "1.0"},
                                    {"before_version": "2"}, {"collection": "all"}, {"page": "2"}])
def test_bad_directory_input_is_rejected_before_query(plan_api, query):
    assert_error(plan_api.get(**query), "invalid_input", 400)
    assert plan_api.statements == []


def test_duplicate_parameters_and_methods_are_not_silently_accepted(plan_api):
    response = plan_api.client.get(BASE + "?size=1&size=2")
    assert_error(response, "invalid_input", 400)
    assert plan_api.client.post(BASE).status_code == 405


def test_actual_http_envelope_bytes_are_bounded(plan_api, monkeypatch):
    from web.routes.workbench import plan_reads

    original = plan_api.get()
    assert original.status_code == 200
    monkeypatch.setattr(plan_reads, "MAX_PLAN_RESPONSE_BYTES", len(original.get_data()) - 1)
    assert_error(plan_api.get(), "query_too_large", 413)


@pytest.mark.parametrize("version", [(1 << 53) - 1, 1 << 53, (1 << 53) + 1, (1 << 63) - 1])
def test_plan_version_and_sequence_use_lossless_int64_wire(plan_api, version):
    with plan_api.db() as conn:
        history(conn, version, op_id=1)
        conn.execute("UPDATE BatchOperations SET seq=? WHERE id=1", (version,))
    ref = plan_api.ref(version)
    expected = version if version <= (1 << 53) - 1 else str(version)
    first = plan_api.read(size=1)
    plan = first["data"]["plans"][0]
    assert plan["version"] == expected and type(plan["version"]) is type(expected)
    assert plan["plan_ref"] == ref and plan["is_current_official"]
    workspace = plan_api.read("/" + ref + "/workspace")["data"]
    assert workspace["plan"]["version"] == expected
    assert workspace["tasks"][0]["sequence"] == expected
    second = plan_api.read(size=1, cursor=first["data"]["page"]["next_cursor"])
    assert second["data"]["plans"][0]["version"] == 3
    with plan_api.db() as conn:
        conn.execute("UPDATE WorkbenchPlanSourceRefs SET active=0 WHERE ref=?", (ref,))
    disabled = plan_api.read(size=1)["data"]["plans"][0]
    assert disabled["version"] == expected and type(disabled["version"]) is type(expected)
    assert disabled["plan_ref"] is None and not disabled["capabilities"]["view"]

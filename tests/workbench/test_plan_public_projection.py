"""Public projection, fail-closed identity boundaries and bounded query evidence."""

import json
import platform
import sqlite3
from dataclasses import replace
from time import perf_counter

import pytest

from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.models.workbench_plan_scope import MAX_PLAN_TASKS
from core.services.scheduler.workbench_plan_catalog import PlanCatalogIssue
from core.services.scheduler.workbench_plan_page import build_history_plan_page
from core.services.workbench import plan_projection, plan_queries
from data.repositories import schedule_time_sql
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.workbench.plan_catalog_support import history, scenario
from tests.workbench.plan_page_support import create_scale_database
from tests.workbench.plan_read_support import (
    add_tasks,
    assert_capacity_blocked,
    assert_error,
    assert_no_private_facts,
    make_api,
    plan_read_api,
    prepare_capacity_case,
)
from web.public_token_registry import issue_public_token


def test_plan_and_task_identity_remain_distinct_across_source_aliases(plan_api):
    locators = [(1, "adopted", None), (3, "adopted", None), (3, "baseline_best", None),
                (3, "critical_best", None), (3, "adopted", "PRIVATE-ACTIVE")]
    tasks = []
    for locator in locators:
        ref = plan_api.ref(*locator)
        data = plan_api.read("/" + ref + "/workspace")["data"]
        assert data["tasks"][0]["plan_ref"] == ref
        tasks.append(data["tasks"][0])
    assert len({task["plan_ref"] for task in tasks}) == len(locators)
    assert len({task["task_ref"] for task in tasks}) == len(locators)
    assert len({task["operation_ref"] for task in tasks}) == 1
    assert tasks[1]["start"] == tasks[2]["start"]
    assert tasks[3]["start"] == "2026-09-11T01:00:00"
    assert tasks[4]["start"] == "2026-09-12T23:00:00"
    assert set(tasks[1]) == {"task_ref", "operation_ref", "plan_ref", "batch_id", "sequence", "process_label",
                             "machine_ref", "operator_ref", "supplier_ref", "start", "end", "piece_id", "quantity",
                             "batch_quantity", "quantity_basis", "quantity_reason"}
    assert tasks[1]["quantity"] is None and tasks[1]["batch_quantity"] is None
    assert tasks[1]["quantity_basis"] == "unknown"
    assert tasks[1]["quantity_reason"] == "plan_target_not_recorded"


def test_private_error_strings_and_fields_cannot_escape_projection(plan_api):
    with plan_api.db() as conn:
        entry = build_history_plan_page(conn, page_size=1).entries[0]
    issue = PlanCatalogIssue("plan_unavailable", "PRIVATE-secret scenario_id=99 schedule_id=101 candidate_id=12")
    malicious = replace(entry, can_view=False, blocked_reasons=(issue,))
    result = plan_projection.project_plan(malicious, plan_api.ref())
    assert_no_private_facts(result)
    assert result["capabilities"]["view"] is False and result["is_current_official"] is False
    assert "99" not in json.dumps(result["blocked_reasons"])


@pytest.mark.parametrize("summary", ["{bad", "[]", "null", "", None])
def test_bad_or_missing_summary_is_visible_unavailable_not_fabricated(plan_api, summary):
    ref = plan_api.ref()
    with plan_api.db() as conn:
        conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=3", (summary,))
    selected = next(row for row in plan_api.read()["data"]["plans"] if row["plan_ref"] == ref)
    assert not selected["capabilities"]["view"] and selected["blocked_reasons"]
    assert_error(plan_api.get("/" + ref + "/workspace"), "plan_unavailable")


@pytest.mark.parametrize("status,summary,expected", [("success", "{}", "complete"), ("partial", "{}", "partial"),
                                                    ("failed", "{}", "invalid"), ("success", '{"is_simulation":true}', "unknown")])
def test_completeness_is_not_permission_or_source_kind(plan_api, status, summary, expected):
    with plan_api.db() as conn:
        conn.execute("UPDATE ScheduleHistory SET result_status=?,result_summary=? WHERE version=3", (status, summary))
    official = plan_api.read()["data"]["plans"][0]
    assert official["completeness"] == expected and official["kind"] == "official"
    assert official["is_current_official"] == (expected == "complete")
    assert not any(official["capabilities"][key] for key in ("adopt", "edit_draft", "report_actual"))


@pytest.mark.parametrize("start,end", [("bad", "2026-09-10 06:30:00"), ("2026-02-30 00:00:00", "2026-03-01 00:00:00"),
                                       ("2026-09-10 06:30:00", "2026-09-10 06:30:00"), ("", "")])
def test_mixed_bad_detail_never_disappears_outside_time_scope(plan_api, start, end):
    ref = plan_api.ref()
    with plan_api.db() as conn:
        add_tasks(conn, 1, start=start, end=end)
    assert not plan_api.read()["data"]["plans"][0]["capabilities"]["view"]
    assert_error(plan_api.get("/" + ref + "/workspace", range_start="2026-09-09T23:00:00",
                             range_end="2026-09-10T01:00:00"), "plan_unavailable")


def test_empty_detail_keeps_catalog_identity_but_refuses_workspace(plan_api):
    with plan_api.db() as conn:
        history(conn, 4)
    latest = plan_api.read()["data"]["plans"][0]
    assert latest["version"] == 4 and latest["plan_ref"]
    assert latest["completeness"] == "invalid" and not latest["capabilities"]["view"]
    assert_error(plan_api.get("/" + latest["plan_ref"] + "/workspace"), "plan_unavailable")


def test_unselected_candidate_source_reference_is_not_a_public_plan(plan_api):
    with plan_api.db() as conn:
        candidate_id = conn.execute("INSERT INTO ScheduleCandidate(version,candidate_key,candidate_label,candidate_kind,status,detail_saved) "
                                    "VALUES (3,'unselected','Unselected','baseline','completed','yes')").lastrowid
        raw_ref = conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='candidate' AND source_key=? AND active=1",
                               (str(candidate_id),)).fetchone()[0]
    assert len(plan_api.read(size=1)["data"]["plans"]) == 3
    assert_error(plan_api.get("/" + raw_ref + "/workspace"), "entity_not_found", 404)


def test_resource_identity_gap_rejects_entire_task_scope_without_repair(plan_api):
    ref = plan_api.ref()
    with plan_api.db() as conn:
        conn.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE kind='machine'")
    before = plan_api.state()
    assert_error(plan_api.get("/" + ref + "/workspace"), "identity_missing")
    assert plan_api.state() == before


def test_missing_task_identity_is_not_allocated_during_read(plan_api, tmp_path):
    ref = plan_api.ref()
    original = plan_api.state()
    damaged_path = tmp_path / "missing-task-identity.sqlite"
    # Reinsert would append immutable dashboard identities. Damage a disposable
    # full backup instead; the original fixture, clocks and triggers stay intact.
    with plan_api.db() as source:
        columns = [row[1] for row in source.execute("PRAGMA table_info(WorkbenchTaskRefs)")]
        tasks = [tuple(row) for row in source.execute("SELECT * FROM WorkbenchTaskRefs WHERE plan_ref=? ORDER BY ref", (ref,))]
        assert "ref" in columns and tasks
        target = sqlite3.connect(str(damaged_path))
        try:
            source.backup(target)
            target.execute("PRAGMA foreign_keys=ON")
            with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
                target.execute("DELETE FROM WorkbenchTaskRefs WHERE plan_ref=?", (ref,))
            target.rollback()
            target.execute("PRAGMA foreign_keys=OFF")
            try:
                target.execute("DELETE FROM WorkbenchTaskRefs WHERE plan_ref=?", (ref,))
                target.commit()
            finally:
                target.rollback()
                target.execute("PRAGMA foreign_keys=ON")
            assert target.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            orphans = list(target.execute("PRAGMA foreign_key_check"))
            assert orphans and all(row[2] == "WorkbenchTaskRefs" for row in orphans)
        finally:
            target.close()
    damaged = make_api(damaged_path)
    before = damaged.state()
    try:
        assert_error(damaged.get("/" + ref + "/workspace"), "identity_missing")
        assert damaged.state() == before
        assert not any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER"))
                       for sql in damaged.statements)
        with damaged.db() as conn:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert [tuple(row) for row in conn.execute("PRAGMA foreign_key_check")] == orphans
    finally:
        assert plan_api.state() == original
        with plan_api.db() as conn:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert not conn.execute("PRAGMA foreign_key_check").fetchall()
            assert [tuple(row) for row in conn.execute("SELECT * FROM WorkbenchTaskRefs WHERE plan_ref=? ORDER BY ref", (ref,))] == tasks


@pytest.mark.parametrize("field,value", [("seq", 0), ("op_type_name", "")])
def test_broken_operation_metadata_cannot_produce_healthy_tasks(plan_api, field, value):
    ref = plan_api.ref()
    with plan_api.db() as conn:
        conn.execute("UPDATE BatchOperations SET " + field + "=?", (value,))
    assert_error(plan_api.get("/" + ref + "/workspace"), "plan_unavailable")


def test_task_payload_budget_refuses_instead_of_slicing(plan_api, monkeypatch):
    monkeypatch.setattr(plan_projection, "MAX_PLAN_RESPONSE_BYTES", 100)
    assert_error(plan_api.get("/" + plan_api.ref() + "/workspace"), "query_too_large", 413)


def test_plan_admission_refuses_over_limit_before_parsing_any_detail(tmp_path, monkeypatch):
    path = tmp_path / "oversized-plan.db"
    conn = create_scale_database(path, history_count=1, rows_per_history=MAX_PLAN_TASKS + 1, scenario_count=0)
    try:
        install_plan_identity(conn)
        conn.commit()
    finally:
        conn.close()
    api = make_api(path)
    ref = api.ref(1)

    def forbidden(value):
        pytest.fail("Admission must stop before per-row time validation")

    monkeypatch.setattr(schedule_time_sql, "parse_dt_for_sql", forbidden)
    entry = api.read(size=1)["data"]["plans"][0]
    assert entry["plan_ref"] == ref
    assert_capacity_blocked(entry)
    assert_error(api.get("/" + ref + "/workspace"), "query_too_large", 413)
    assert any("LIMIT 10001" in sql for sql in api.statements)


@pytest.mark.parametrize("oversized,blocked_roles", [
    ("official", {"adopted", "baseline_best"}), ("candidate", {"critical_best"}), ("scenario", set()),
])
def test_catalog_capacity_is_per_actual_role(plan_api, monkeypatch, oversized, blocked_roles):
    before = prepare_capacity_case(plan_api, monkeypatch, oversized)
    refs = {role: plan_api.ref(role=role) for role in ("adopted", "baseline_best", "critical_best")}
    first = plan_api.read(size=1)
    plans = {row["plan_ref"]: row for row in first["data"]["plans"]}
    assert set(plans) == set(refs.values())
    for role, ref in refs.items():
        entry = plans[ref]
        if role in blocked_roles:
            assert_capacity_blocked(entry)
            assert_error(plan_api.get("/" + ref + "/workspace"), "query_too_large", 413)
        else:
            assert entry["capabilities"]["view"] and not entry["blocked_reasons"]
            assert plan_api.read("/" + ref + "/workspace")["data"]["task_count"] == 1
    second = plan_api.read(size=1, cursor=first["data"]["page"]["next_cursor"])
    assert second["data"]["plans"][0]["version"] == 2 and second["data"]["plans"][0]["capabilities"]["view"]
    assert not second["data"]["plans"][0]["is_current_official"]
    assert plan_api.state() == before


@pytest.mark.parametrize("oversized,blocked", [("official", True), ("candidate", False), ("scenario", True)])
def test_scenario_capacity_is_local_to_preview_and_its_base(plan_api, monkeypatch, oversized, blocked):
    before = prepare_capacity_case(plan_api, monkeypatch, oversized)
    active_ref = plan_api.ref(scenario_id="PRIVATE-ACTIVE")
    small_ref = plan_api.ref(2, scenario_id="Z-SMALL")
    page = plan_api.read(collection="scenario", size=1)
    scenarios = list(page["data"]["plans"])
    while page["data"]["page"]["has_more"]:
        page = plan_api.read(collection="scenario", size=1, cursor=page["data"]["page"]["next_cursor"])
        scenarios.extend(page["data"]["plans"])
    scenarios = {row["plan_ref"]: row for row in scenarios}
    active = scenarios[active_ref]
    assert active["capabilities"]["view"] == (not blocked)
    if blocked:
        assert_capacity_blocked(active)
        assert_error(plan_api.get("/" + active_ref + "/workspace"), "query_too_large", 413)
    else:
        assert plan_api.read("/" + active_ref + "/workspace")["data"]["task_count"] == 1
    assert scenarios[small_ref]["capabilities"]["view"]
    assert plan_api.read("/" + small_ref + "/workspace")["data"]["task_count"] == 1
    for ref, entry in scenarios.items():
        if ref not in (active_ref, small_ref):
            assert not entry["capabilities"]["view"]
            assert entry["blocked_reasons"][0]["code"] == "scenario_not_active"
    assert plan_api.state() == before


@pytest.mark.parametrize("function,collection", [("_admit_version", "history"), ("_admit_scenario", "scenario")])
def test_other_admission_failures_are_not_capacity_entries(plan_api, monkeypatch, function, collection):
    def reject(*args):
        raise WorkbenchCommandRejected("constraint_conflict", "Other admission failure")

    monkeypatch.setattr(plan_queries, function, reject)
    assert_error(plan_api.get(collection=collection), "constraint_conflict")


def test_bad_candidate_binding_does_not_poison_other_history_versions(plan_api):
    broken_ref = plan_api.ref(role="critical_best")
    healthy_ref = plan_api.ref(2)
    with plan_api.db() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM ScheduleCandidate WHERE version=3 AND candidate_key='critical_best'")
        private_page = build_history_plan_page(conn, page_size=3)
        assert not next(row for row in private_page.entries if row.locator.plan_role == "critical_best").can_view
        assert next(row for row in private_page.entries if row.locator.version == 2).can_view
    before = plan_api.state()
    page = plan_api.read(size=3)
    entries = {row["plan_ref"]: row for row in page["data"]["plans"]}
    assert entries[broken_ref]["capabilities"]["view"] is False
    assert entries[broken_ref]["blocked_reasons"][0]["code"] == "plan_binding_invalid"
    assert entries[healthy_ref]["capabilities"]["view"]
    assert not entries[healthy_ref]["is_current_official"]
    assert plan_api.read("/" + healthy_ref + "/workspace")["data"]["task_count"] == 1
    assert_error(plan_api.get("/" + broken_ref + "/workspace"), "plan_binding_invalid")
    first = plan_api.read(size=1)
    second = plan_api.read(size=1, cursor=first["data"]["page"]["next_cursor"])
    assert second["data"]["plans"][0]["plan_ref"] == healthy_ref
    assert make_api(plan_api.path).read(size=3)["data"] == page["data"]
    assert plan_api.state() == before


def test_missing_scenario_base_does_not_poison_other_scenarios(plan_api):
    broken_ref = plan_api.ref(scenario_id="PRIVATE-ACTIVE")
    with plan_api.db() as conn:
        scenario(conn, "Z-GOOD", 2, op_id=1)
        conn.execute("DELETE FROM ScheduleHistory WHERE version=3")
    healthy_ref = plan_api.ref(2, scenario_id="Z-GOOD")
    before = plan_api.state()
    entries = {row["plan_ref"]: row for row in plan_api.read(collection="scenario")["data"]["plans"]}
    assert entries[broken_ref]["capabilities"]["view"] is False
    assert entries[broken_ref]["blocked_reasons"][0]["code"] == "history_missing"
    assert entries[healthy_ref]["capabilities"]["view"]
    assert plan_api.read("/" + healthy_ref + "/workspace")["data"]["task_count"] == 1
    assert_error(plan_api.get("/" + broken_ref + "/workspace"), "plan_binding_invalid")
    assert plan_api.state() == before


def test_missing_catalog_identity_stays_disabled_without_fabricating_ref(plan_api):
    old_ref = plan_api.ref(role="critical_best")
    healthy_ref = plan_api.ref(2)
    with plan_api.db() as conn:
        conn.execute("UPDATE WorkbenchPlanSourceRefs SET active=0 WHERE ref=?", (old_ref,))
    before = plan_api.state()
    entries = plan_api.read(size=3)["data"]["plans"]
    broken = next(row for row in entries if row["display_name"] == "critical_best label")
    assert broken["plan_ref"] is None
    assert broken["capabilities"]["view"] is False
    assert broken["blocked_reasons"][0]["code"] == "identity_missing"
    assert next(row for row in entries if row["plan_ref"] == healthy_ref)["capabilities"]["view"]
    assert_error(plan_api.get("/" + old_ref + "/workspace"), "entity_not_found", 404)
    assert plan_api.state() == before


def test_nonnumeric_candidate_binding_is_a_disabled_entry_not_page_failure(plan_api):
    healthy_ref = plan_api.ref(2)
    with plan_api.db() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("UPDATE ScheduleCandidateSelection SET candidate_id='broken' WHERE version=3 AND role='critical_best'")
        binding = WorkbenchPlanIdentityRepository(conn).get_catalog_reference(WorkbenchPlanLocator(3, "critical_best"))
    assert binding.plan_ref is not None and not binding.binding_valid
    before = plan_api.state()
    entries = {row["plan_ref"]: row for row in plan_api.read(size=3)["data"]["plans"]}
    assert entries[binding.plan_ref]["capabilities"]["view"] is False
    assert entries[binding.plan_ref]["blocked_reasons"][0]["code"] == "plan_binding_invalid"
    assert entries[healthy_ref]["capabilities"]["view"]
    assert_error(plan_api.get("/" + binding.plan_ref + "/workspace"), "plan_binding_invalid")
    assert plan_api.state() == before


def test_invalid_scenario_version_stays_unknown_and_does_not_hide_healthy_scenario(plan_api):
    with plan_api.db() as conn:
        scenario(conn, "Z-GOOD", 2, op_id=1)
        conn.execute("UPDATE ScheduleAdjustmentScenario SET base_version='broken' WHERE scenario_id='PRIVATE-ACTIVE'")
    healthy_ref = plan_api.ref(2, scenario_id="Z-GOOD")
    before = plan_api.state()
    entries = plan_api.read(collection="scenario")["data"]["plans"]
    broken = next(row for row in entries if row["display_name"] == "active display")
    assert broken["plan_ref"] is None and broken["version"] is None
    assert broken["capabilities"]["view"] is False
    assert broken["blocked_reasons"][0]["code"] == "identity_invalid"
    assert next(row for row in entries if row["plan_ref"] == healthy_ref)["capabilities"]["view"]
    assert plan_api.state() == before


@pytest.mark.parametrize("version", [None, True, False, 0, -1, 1.5, "3", 1 << 63])
def test_disabled_invalid_version_has_no_fabricated_wire_number(version):
    value = plan_projection.project_unavailable_plan(
        WorkbenchPlanLocator(version, "adopted"), None, "Unavailable", ("identity_invalid",),
    )
    assert value["version"] is None and value["capabilities"]["view"] is False


@pytest.mark.parametrize("version", [0, True, 1 << 63])
def test_healthy_identity_cannot_serialize_invalid_version(plan_api, version):
    with plan_api.db() as conn:
        entry = build_history_plan_page(conn, page_size=1).entries[0]
    entry = replace(entry, locator=replace(entry.locator, version=version))
    with pytest.raises(WorkbenchCommandRejected) as failure:
        plan_projection.project_plan(entry, plan_api.ref())
    assert failure.value.code == "plan_unavailable"


def test_scope_returns_every_row_at_admission_boundary(plan_api, monkeypatch):
    monkeypatch.setattr(plan_queries, "MAX_PLAN_TASKS", 3)
    ref = plan_api.ref()
    with plan_api.db() as conn:
        add_tasks(conn, 2)
    data = plan_api.read("/" + ref + "/workspace")["data"]
    assert data["task_count"] == 3 and len(data["tasks"]) == 3 and data["tasks_complete"]
    assert data["plan_span"]["end"] == "2026-09-12T02:00:00"


def test_public_pages_scale_ten_thousand_versions_without_fullhistory(tmp_path):
    path = tmp_path / "public-plan-scale.db"
    conn = create_scale_database(path, history_count=10000, rows_per_history=2, scenario_count=0)
    try:
        install_plan_identity(conn)
        conn.commit()
    finally:
        conn.close()
    api = make_api(path)
    start = perf_counter()
    first = api.read()
    first_time, first_sql = perf_counter() - start, len(api.statements)
    with api.app.app_context():
        cursor = issue_public_token("workbench-plan-catalog-cursor-v1", json.dumps({
            "scope": {"source": "production", "kind": "plan_catalog", "collection": "history", "size": 20},
            "seek": 101, "snapshot_ref": first["meta"]["snapshot_ref"]}), ttl_seconds=900)
    api.statements.clear()
    start = perf_counter()
    deep = api.read(cursor=cursor)
    deep_time, deep_sql = perf_counter() - start, len(api.statements)
    assert [row["version"] for row in first["data"]["plans"]] == list(range(10000, 9980, -1))
    assert [row["version"] for row in deep["data"]["plans"]] == list(range(100, 80, -1))
    assert abs(first_sql - deep_sql) <= 3 and deep_sql < 400
    assert not any("OFFSET" in sql.upper() for sql in api.statements)
    print("PUBLIC_PLAN_SCALE " + json.dumps({"versions": 10000, "rows": 20000, "python": platform.python_version(),
          "sqlite": sqlite3.sqlite_version, "machine": platform.machine(), "first_ms": round(first_time * 1000, 3),
          "deep_ms": round(deep_time * 1000, 3), "first_sql": first_sql, "deep_sql": deep_sql}, sort_keys=True))

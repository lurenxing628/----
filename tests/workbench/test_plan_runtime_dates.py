"""Full application reads retain real SQLite converters and private fact types."""

import sqlite3
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from core.infrastructure.database import get_connection
from core.models.workbench_command import canonical_json, input_fingerprint
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench import plan_queries
from core.services.workbench.plan_fact_serialization import plain_plan_facts
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.workbench.plan_read_support import (
    BASE,
    NIGHT_END,
    NIGHT_START,
    assert_error,
    assert_no_private_facts,
    seed_plans,
)
from tests.workbench.test_plan_export_api import read_rows


@contextmanager
def runtime_db(path):
    with closing(get_connection(path)) as conn:
        with conn:
            yield conn


@pytest.fixture
def runtime_plan(app_client, db_env):
    path = app_client.application.config["DATABASE_PATH"]
    assert path == db_env
    with runtime_db(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        seed_plans(conn)
        conn.execute("UPDATE Batches SET due_date='2026-09-10'")
        conn.execute("UPDATE BatchOperations SET source='internal'")
        conn.execute("INSERT INTO WorkCalendar(date,shift_start,shift_hours,remark) VALUES ('2026-09-09','22:00',8,?)",
                     (b"\x00\xffprivate-calendar",))
        conn.execute("INSERT INTO OperatorCalendar(operator_id,date,shift_start,shift_hours) "
                     "VALUES ('PRIVATE-O1','2026-09-09','22:00',8)")
        ref = WorkbenchPlanIdentityRepository(conn).get_plan_ref(WorkbenchPlanLocator(3, "adopted"))
    return SimpleNamespace(client=app_client, path=path, ref=ref)


def read_payload(response):
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    body = response.get_json()
    assert body["ok"] and body["meta"]["source"] == "production"
    assert_no_private_facts(body)
    serialized = canonical_json(body)
    for key in ("storage_type", "projection_facts", "invalid_number", "iso", "hex"):
        assert '"' + key + '":' not in serialized
    return body


def test_real_connection_scalar_types_have_lossless_private_encoding(db_path):
    with runtime_db(db_path) as conn:
        row = dict(conn.execute('SELECT ? AS "day [DATE]", ? AS "instant [TIMESTAMP]", '
                                '? AS blob, ? AS nonfinite, ? AS missing',
                                ("2026-09-09", "2026-09-09 22:30:00.123456", b"\x00\xff", float("inf"), None)).fetchone())
    assert type(row["day"]) is date and type(row["instant"]) is datetime
    assert type(row["blob"]) is bytes and type(row["nonfinite"]) is float
    facts = {"rows": [row], "nested": (row["instant"], [row["day"]])}
    plain = plain_plan_facts(facts)
    assert plain["rows"][0] == {
        "day": {"storage_type": "date", "iso": "2026-09-09"},
        "instant": {"storage_type": "datetime", "iso": "2026-09-09T22:30:00.123456"},
        "blob": {"storage_type": "blob", "hex": "00ff"},
        "nonfinite": {"storage_type": "float", "value": "inf"}, "missing": None,
    }
    assert plain["nested"] == [plain["rows"][0]["instant"], [plain["rows"][0]["day"]]]
    assert input_fingerprint(plain) == input_fingerprint(plain_plan_facts(facts))
    assert type(facts["nested"]) is tuple and type(row["day"]) is date


@pytest.mark.parametrize("value,expected", [
    (None, None), (True, True), (42, 42), (-0.0, -0.0), (1.25, 1.25), ("2026-09-09", "2026-09-09"),
    (float("nan"), {"storage_type": "float", "value": "nan"}),
    (float("-inf"), {"storage_type": "float", "value": "-inf"}),
    (datetime(2026, 9, 9, 22, 30, 0, 123456, timezone(timedelta(hours=8))),
     {"storage_type": "datetime", "iso": "2026-09-09T22:30:00.123456+08:00"}),
])
def test_private_scalar_encoding_is_explicit(value, expected):
    assert plain_plan_facts(value) == expected
    canonical_json(plain_plan_facts(value))


@pytest.mark.parametrize("left,right", [
    (date(2026, 9, 9), "2026-09-09"),
    (date(2026, 9, 9), datetime(2026, 9, 9)),
    (datetime(2026, 9, 9, 22, 30), "2026-09-09T22:30:00"),
    (datetime(2026, 9, 9, 22, 30), datetime(2026, 9, 9, 22, 30, 0, 1)),
    (b"\x00\xff", "00ff"), (float("nan"), "nan"), (float("inf"), float("-inf")),
])
def test_private_types_and_subsecond_changes_have_distinct_fingerprints(left, right):
    assert input_fingerprint(plain_plan_facts(left)) != input_fingerprint(plain_plan_facts(right))


@pytest.mark.parametrize("value", [object(), Decimal("1.5"), {1, 2}])
def test_unsupported_private_objects_are_not_stringified(value):
    with pytest.raises(TypeError, match="Unsupported private plan fact type"):
        plain_plan_facts({"nested": [(value,)]})


def observe_private_dates(monkeypatch, *, has_operator):
    observed = []

    def record_private_types(facts):
        sources = facts["calendar"]["sources"]
        assert type(sources["global"][0]["date"]) is date
        if has_operator:
            assert type(sources["personal"][0]["date"]) is date
        else:
            assert sources["personal"] == []
        assert type(sources["global"][0]["remark"]) is bytes
        result = plain_plan_facts(facts)
        assert type(sources["global"][0]["date"]) is date
        observed.append(result["calendar"]["sources"]["global"][0]["date"])
        return result

    monkeypatch.setattr(plan_queries, "plain_plan_facts", record_private_types)
    return observed


def assert_pinned_reads(client, path, first, pinned):
    for suffix in ("/workspace", ""):
        repeated = read_payload(client.get(path + suffix, query_string=pinned))
        assert repeated["data"] == first["data"]
        assert repeated["meta"]["request_ref"] != first["meta"]["request_ref"]
        assert {key: value for key, value in repeated["meta"].items() if key != "request_ref"} == {
            key: value for key, value in first["meta"].items() if key != "request_ref"}


def assert_pinned_exports(client, path, first, pinned):
    task = first["data"]["tasks"][0]
    for fmt in ("csv", "xlsx"):
        response = client.get(path + "/export", query_string=dict(pinned, format=fmt))
        rows = read_rows(response, fmt)
        assert len(rows) == 2 and response.headers["X-Workbench-Row-Count"] == "1"
        assert response.headers["X-Workbench-Snapshot-Ref"] == pinned["snapshot_ref"]
        assert list(rows[1][6:8]) == [pinned["snapshot_ref"], first["meta"]["as_of"]]
        assert list(rows[1][22:24]) == [task["start"], task["end"]]
        assert rows[1][27] == "2026-09-10"
        assert "storage_type" not in str(rows)


@pytest.mark.parametrize("role,scenario", [
    ("adopted", None), ("baseline_best", None), ("critical_best", None), ("adopted", "PRIVATE-ACTIVE"),
])
def test_full_app_converted_dates_same_snapshot_and_exports(runtime_plan, monkeypatch, role, scenario):
    api = runtime_plan
    with runtime_db(api.path) as conn:
        ref = WorkbenchPlanIdentityRepository(conn).get_plan_ref(WorkbenchPlanLocator(3, role, scenario))
        before = list(conn.iterdump())
    has_operator = scenario is None and role != "critical_best"
    observed = observe_private_dates(monkeypatch, has_operator=has_operator)
    path = BASE + "/" + ref
    scope = {"range_start": "2026-09-09T00:00:00", "range_end": "2026-09-14T00:00:00"}
    first = read_payload(api.client.get(path + "/workspace", query_string=scope))
    pinned = dict(scope, snapshot_ref=first["meta"]["snapshot_ref"])
    assert_pinned_reads(api.client, path, first, pinned)
    data = first["data"]
    assert data["task_count"] == 1
    task = data["tasks"][0]
    if has_operator:
        assert (task["start"], task["end"]) == (NIGHT_START, NIGHT_END)
    assert datetime.fromisoformat(task["start"]).isoformat() == task["start"]
    assert data["projections"]["delivery_risks"]["items"][0]["due_date"] == "2026-09-10"
    assert_pinned_exports(api.client, path, first, pinned)
    assert observed == [{"storage_type": "date", "iso": "2026-09-09"}] * 5
    with runtime_db(api.path) as conn:
        assert list(conn.iterdump()) == before


@pytest.mark.parametrize("sql,old,new,revision_delta", [
    ("UPDATE WorkCalendar SET remark=?", b"\x00\xff", "00ff", 0),
    ("UPDATE WorkCalendar SET remark=?", b"private-before", b"private-after", 0),
    ("UPDATE WorkCalendar SET efficiency=?", float("inf"), float("-inf"), 0),
    ("UPDATE BatchOperations SET op_code=?", b"private-before", b"private-after", 1),
    ("UPDATE BatchOperations SET op_code=?", b"private-code", "private-code", 1),
])
def test_hidden_typed_facts_stale_full_app_workspace_and_exports(runtime_plan, sql, old, new, revision_delta):
    api = runtime_plan
    with runtime_db(api.path) as conn:
        conn.execute(sql, (old,))
    path = BASE + "/" + api.ref
    first = read_payload(api.client.get(path + "/workspace"))
    pinned = {"snapshot_ref": first["meta"]["snapshot_ref"]}
    assert_pinned_exports(api.client, path, first, pinned)
    with runtime_db(api.path) as conn:
        revision = WorkbenchPlanIdentityRepository(conn).read_revision()
        conn.execute(sql, (new,))
        assert WorkbenchPlanIdentityRepository(conn).read_revision() == revision + revision_delta
        changed = list(conn.iterdump())
    second = read_payload(api.client.get(path + "/workspace"))
    assert first["data"] == second["data"]
    assert first["meta"]["snapshot_ref"] != second["meta"]["snapshot_ref"]
    assert_error(api.client.get(path + "/workspace", query_string=pinned), "snapshot_stale")
    for fmt in ("csv", "xlsx"):
        assert_error(api.client.get(path + "/export", query_string=dict(pinned, format=fmt)), "snapshot_stale")
    with runtime_db(api.path) as conn:
        assert list(conn.iterdump()) == changed


def test_full_app_datetime_conversion_keeps_public_iso(runtime_plan, monkeypatch):
    # DATE/TIMESTAMP are built in; also exercise DATETIME when registered by a host.
    monkeypatch.setitem(sqlite3.converters, "DATETIME", lambda raw: datetime.fromisoformat(raw.decode("ascii")))
    api = runtime_plan
    with runtime_db(api.path) as conn:
        assert type(conn.execute("SELECT start_time FROM Schedule WHERE version=3").fetchone()[0]) is datetime
        before = list(conn.iterdump())
    path = BASE + "/" + api.ref
    first = read_payload(api.client.get(path + "/workspace"))
    task = first["data"]["tasks"][0]
    assert (task["start"], task["end"]) == (NIGHT_START, NIGHT_END)
    pinned = {"snapshot_ref": first["meta"]["snapshot_ref"]}
    assert_pinned_reads(api.client, path, first, pinned)
    assert_pinned_exports(api.client, path, first, pinned)
    with runtime_db(api.path) as conn:
        assert list(conn.iterdump()) == before


def test_real_converter_read_transaction_keeps_private_fact_snapshot(runtime_plan):
    api = runtime_plan
    scope = PlanReadScope(api.ref)
    with runtime_db(api.path) as conn:
        reader = WorkbenchPlanQueryService(conn)
        with reader.read_snapshot():
            first_data, first_state = reader.workspace(scope)
            with runtime_db(api.path) as writer:
                writer.execute("UPDATE WorkCalendar SET remark=?", (b"changed-by-writer",))
            assert reader.workspace(scope) == (first_data, first_state)
        with reader.read_snapshot():
            next_data, next_state = reader.workspace(scope)
        assert next_data == first_data and next_state != first_state

"""R1-F: strict facts and real factory connections on a private current database."""

import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone

import pytest
from flask import g

from core.infrastructure.database import get_connection
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_outsourcing_input import factory_time, next_values
from tests.workbench.dashboard_support import close_payload
from tests.workbench.outsourcing_live_support import seed_outsourcing_data
from tests.workbench.outsourcing_targets_labels_support import storage
from web.bootstrap import factory

ROOT = "/api/workbench/v1/outsourcing"
DASHBOARD = "/api/workbench/v1/dashboard"
NOW = datetime(2026, 9, 10, 12)
FACTS = {"sent": "2026-09-07T09:00:00", "planned": "2026-09-09T12:00:00",
         "returned": None, "confirmedState": "in_transit"}
CREATE_TABLES = {"WorkbenchOutsourcingReceipts", "WorkbenchOutsourcingMembers", "WorkbenchOutsourcingFacts",
                 "WorkbenchCommandReceipts", "WorkbenchDashboardExternalItems"}
CORRECTION_TABLES = {"WorkbenchOutsourcingFacts", "WorkbenchCommandReceipts"}
HANDLING_TABLES = {"WorkbenchDashboardExternalStates", "WorkbenchDashboardExternalHistory", "WorkbenchCommandReceipts"}


class FactoryCase:
    def __init__(self, app, conn, path):
        self.conn, self.path, self.client = conn, path, app.test_client()
        self.opened, self.changes, self.statements = [], [], []
        self.read_only = False

        @app.before_request
        def observe_connection():
            connection = g.db
            if self.read_only:
                connection.execute("PRAGMA query_only=ON")
            assert connection.execute("PRAGMA database_list").fetchone()[2] == path
            assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert type(connection.execute("SELECT due_date FROM Batches WHERE batch_id='XB1'").fetchone()[0]) is date
            self.opened.append(connection)

            # pragma_table_info emits authorizer UPDATE callbacks without executing writes.
            connection.set_trace_callback(self.statements.append)

        @app.teardown_request
        def observe_changes(error):
            self.changes.append(g.db.total_changes)

    def send(self, method, path, *, tables=(), status=200, **kwargs):
        before = storage(self.conn)
        start = len(self.opened)
        self.changes.clear()
        self.statements.clear()
        self.read_only = method == "GET" or path == ROOT + "/receipts/preview"
        response = self.client.open(path, method=method, **kwargs)
        assert response.status_code == status, response.get_json()
        after = storage(self.conn)
        assert set(before) == set(after)
        assert {table for table in before if before[table] != after[table]} == set(tables)
        assert len(self.opened) == start + 1
        assert len(self.changes) == 1
        assert (self.changes[0] > 0) is bool(tables), self.statements
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            self.opened[-1].execute("SELECT 1")
        return response.get_json()

    def payload(self, merged=True):
        targets = self.send("GET", ROOT + "/targets")["data"]["items"]
        members = targets[:2] if merged else targets[:1]
        return {**FACTS, "declared_operator": "Shipping clerk", "reason": "Verified original dispatch record",
                "target": {"kind": "merged" if merged else "single", "batch_ref": members[0]["batch_ref"],
                           "supplier_ref": members[0]["supplier_ref"], "operation_refs": [row["operation_ref"] for row in members]}}

    def preview(self, payload):
        return self.send("POST", ROOT + "/receipts/preview", json={"input": payload})["data"]

    def confirm(self, draft, key, *, tables, status=200):
        return self.send("POST", ROOT + "/receipts", tables=tables, status=status,
                         json={"input": draft["input"], "request_key": key, "write_token": draft["write_context"]["write_token"]})


@pytest.fixture(name="factory_case")
def factory_case(db_env):
    with closing(get_connection(db_env)) as conn:
        seed_outsourcing_data(conn)
        app = factory.create_app_core(ui_mode="default", enable_secret_key=False,
                                      enable_security_headers=False, enable_session_cookie_hardening=False)
        app.config["TESTING"] = True
        yield FactoryCase(app, conn, db_env)


@pytest.mark.parametrize("value", [None, False, 0, 0.0, b"2026-09-07T09:00:00", NOW, NOW.date(), "",
    "2026-02-29T09:00:00", "2026-09-07", "2026-09-07 09:00:00", "2026-09-07T09:00:00Z",
    "2026-09-07T09:00:00+08:00", "2026-09-07T09:00:00.000", "2026-09-07T24:00:00"])
def test_factory_time_rejects_missing_or_non_factory_values(value):
    with pytest.raises(WorkbenchCommandRejected) as error:
        factory_time(value)
    assert error.value.code == "invalid_input" and error.value.status == 422


def test_values_validate_output_and_do_not_mutate_original_facts():
    parsed = factory_time("2024-02-29T09:00:00")
    assert parsed == datetime(2024, 2, 29, 9) and parsed.tzinfo is None
    before = dict(FACTS)
    patch = {"returned": "2026-09-10T11:00:00", "confirmedState": "returned"}
    assert next_values(before, patch, NOW) == {**before, **patch}
    assert before == FACTS and patch["returned"] == "2026-09-10T11:00:00"
    for invalid in ({"confirmedState": "closed"}, {"sent": None}, {"planned": False}, {"returned": 0}):
        with pytest.raises(WorkbenchCommandRejected):
            next_values({**before, **invalid}, {}, NOW)
    for now in (None, NOW.date(), NOW.replace(tzinfo=timezone.utc)):
        with pytest.raises(ValueError, match="factory-local"):
            next_values(before, {}, now)


def _original_fact(conn, ref, members):
    original_fact = dict(conn.execute("SELECT * FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=?", (ref,)).fetchone())
    evidence = json.loads(original_fact["source_facts_json"])
    assert evidence["batch"]["row"]["quantity"] == {"storage_type": "integer", "value": "10"}
    assert len(evidence["operations"]) == len(members)
    assert json.loads(original_fact["before_json"]) is None
    return original_fact


def _assert_history_chain(history, members):
    facts = history["history"]["items"]
    assert history["item"]["target"]["operation_refs"] == members
    assert history["item"]["history_count"] == len(facts) == 4
    assert facts[-1]["after"] == FACTS and facts[-1]["before"] is None
    assert facts[-2]["after"]["returned"] == "2026-09-10T11:00:00"
    assert facts[0]["before"] == facts[0]["after"] and facts[0]["after"]["returned"] is None
    assert [fact["previous_fact_ref"] for fact in facts[:-1]] == [fact["fact_ref"] for fact in facts[1:]]
    return facts


@pytest.mark.parametrize("merged", [False, True])
def test_factory_registration_correction_history_replay_and_reopen_connection(factory_case, merged):
    case = factory_case
    draft = case.preview(case.payload(merged))
    first = case.confirm(draft, "r1f-create-00000001", tables=CREATE_TABLES)
    ref = first["data"]["outsourcing_ref"]
    original = storage(case.conn)
    original_members = sorted(draft["input"]["target"]["operation_refs"])
    assert len(original_members) == (2 if merged else 1)
    original_fact = _original_fact(case.conn, ref, original_members)
    assert case.confirm(draft, "r1f-create-00000001", tables=())["receipt_ref"] == first["receipt_ref"]
    changed_intent = {**draft, "input": {**draft["input"], "reason": "Different intent"}}
    assert case.confirm(changed_intent, "r1f-create-00000001", tables=(), status=409)["error"]["code"] == "request_key_conflict"

    correction = {"outsourcing_ref": ref, "declared_operator": "Receiver", "reason": "Checked return receipt",
                  "returned": "2026-09-10T11:00:00", "confirmedState": "returned"}
    returned = case.confirm(case.preview(correction), "r1f-return-00000001", tables=CORRECTION_TABLES)
    assert returned["data"]["sent"] == FACTS["sent"] and returned["data"]["planned"] == FACTS["planned"]
    assert returned["data"]["execution"]["automatically_reported"] is False
    correction.update(returned=None, confirmedState="awaiting_confirmation", reason="Corrected unsupported return claim")
    case.confirm(case.preview(correction), "r1f-correct-00000001", tables=CORRECTION_TABLES)
    unchanged = {"outsourcing_ref": ref, "declared_operator": "Supervisor", "reason": "Rechecked original evidence"}
    case.confirm(case.preview(unchanged), "r1f-reconfirm-00000001", tables=CORRECTION_TABLES)

    history_path = ROOT + "/receipts/" + ref + "/history"
    history = case.send("GET", history_path)["data"]
    facts = _assert_history_chain(history, original_members)
    current = storage(case.conn)
    for table in ("WorkbenchOutsourcingReceipts", "WorkbenchOutsourcingMembers", "WorkbenchDashboardExternalItems"):
        assert current[table] == original[table]
    assert dict(case.conn.execute("SELECT * FROM WorkbenchOutsourcingFacts WHERE fact_ref=?", (original_fact["fact_ref"],)).fetchone()) == original_fact
    assert case.send("GET", "/api/workbench/v1/commands/r1f-create-00000001")["data"] == first["data"]
    page = case.send("GET", history_path, query_string={"size": 1})
    second = case.send("GET", history_path, query_string={"size": 1, "page": 2, "snapshot_ref": page["meta"]["snapshot_ref"]})
    assert second["data"]["history"]["items"] == facts[1:2]
    case.conn.close()
    with closing(get_connection(case.path)) as reopened:
        assert storage(reopened) == current
        assert reopened.execute("PRAGMA foreign_key_check").fetchall() == []


def test_factory_closed_handling_does_not_forge_return_and_reopen_preserves_history(factory_case):
    case = factory_case
    first = case.confirm(case.preview(case.payload()), "r1f-handling-create-01", tables=CREATE_TABLES)
    ref = first["data"]["outsourcing_ref"]
    original = storage(case.conn)
    query = {"category": "external", "size": "1"}
    listing = case.send("GET", DASHBOARD, query_string=query)
    item = listing["data"]["items"][0]
    path = DASHBOARD + "/items/" + item["item_ref"]
    closed = case.send("POST", path + "/transition", tables=HANDLING_TABLES,
                       json={"input": close_payload(), "request_key": "r1f-handling-close-01", "write_token": item["write_context"]["write_token"]})
    assert closed["data"]["handling"]["status"] == "closed"
    receipt = case.send("GET", ROOT + "/receipts/" + ref)["data"]["item"]
    assert receipt["returned"] is None and receipt["confirmedState"] == "in_transit"
    listing = case.send("GET", DASHBOARD, query_string=query)
    item = listing["data"]["items"][0]
    history_query = {**query, "snapshot_ref": listing["meta"]["snapshot_ref"]}
    closed_history = case.send("GET", path + "/history", query_string=history_query)["data"]["history"]["items"][0]
    assert closed_history["receipt_ref"] == closed["receipt_ref"]
    reopened = case.send("POST", path + "/reopen", tables=HANDLING_TABLES,
                         json={"input": {"reason": "Recheck original shipment evidence"}, "request_key": "r1f-handling-reopen-01",
                               "write_token": item["write_context"]["write_token"]})
    assert reopened["data"]["handling"]["status"] == "following"
    listing = case.send("GET", DASHBOARD, query_string=query)
    history_query["snapshot_ref"] = listing["meta"]["snapshot_ref"]
    history = case.send("GET", path + "/history", query_string=history_query)["data"]["history"]
    assert history["page"]["total"] == 2 and len(history["items"]) == 1
    second_page = case.send("GET", path + "/history", query_string={**history_query, "history_page": 2})
    assert second_page["data"]["history"]["items"] == [closed_history]
    current = storage(case.conn)
    for table in ("WorkbenchOutsourcingReceipts", "WorkbenchOutsourcingMembers", "WorkbenchOutsourcingFacts",
                  "WorkbenchProductionReports", "OperationExecutionEvents", "Batches", "BatchOperations"):
        assert current[table] == original[table]


def test_factory_rejects_invalid_input_and_queries_without_writes(factory_case):
    case = factory_case
    payload = case.payload()
    invalid_facts = ({"sent": None}, {"planned": 0}, {"sent": "2026-02-29T09:00:00"},
                     {"planned": "2026-09-06T09:00:00"}, {"returned": "2026-09-06T09:00:00", "confirmedState": "returned"},
                     {"sent": "2099-09-01T09:00:00", "planned": "2099-09-02T09:00:00"},
                     {"returned": "2099-09-02T09:00:00", "confirmedState": "returned"},
                     {"confirmedState": "returned"}, {"confirmedState": "closed"}, {"declared_operator": None})
    for patch in invalid_facts:
        body = case.send("POST", ROOT + "/receipts/preview", status=422, json={"input": {**payload, **patch}})
        assert body["committed"] is False
    for target in (None, "bad", {**payload["target"], "supplier_ref": None},
                   {**payload["target"], "operation_refs": []}):
        case.send("POST", ROOT + "/receipts/preview", status=400, json={"input": {**payload, "target": target}})
    for query in ("page=2", "page=0", "size=0", "size=101", "page=1&page=2", "page=1.0", "size=false", "page=1000000", "extra=x"):
        case.send("GET", ROOT + "/receipts?" + query, status=400)
    case.send("GET", ROOT + "/receipts?snapshot_ref=missing", status=409)


def test_factory_missing_actual_operator_never_commits(factory_case, monkeypatch):
    import core.services.workbench.outsourcing_commands as commands

    case = factory_case
    draft = case.preview(case.payload())
    for index, actor in enumerate((None, False, 0, "", " ", "bad\x00actor", "x" * 201)):
        monkeypatch.setattr(commands.getpass, "getuser", lambda actor=actor: actor)
        body = case.confirm(draft, "r1f-invalid-operator-" + str(index), tables=(), status=500)
        assert body["committed"] == "unknown"
        lookup = case.send("GET", body["error"]["result_target"])
        assert lookup["state"] == "not_recorded" and lookup["receipt"] is None and lookup["may_be_in_flight"] is True

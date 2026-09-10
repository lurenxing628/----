"""Real Flask stage requests with isolated SQLite and independent row oracles."""

import sqlite3
import uuid
from contextlib import contextmanager

import pytest

from core.infrastructure.transaction import TransactionManager
from core.services.process.workflow_state import record_confirmation
from tests.workbench.process_query_support import ref_for, seed_process
from tests.workbench.process_route_support import all_table_snapshot

BASE = "/api/workbench/v1"
PART = "PROC-001"
METADATA = {"WorkbenchProcessWorkflow", "WorkbenchProcessOperationConfirmations", "WorkbenchCommandReceipts"}


def seed_history(conn):
    conn.execute("ALTER TABLE PartOperations ADD COLUMN private_stage_note TEXT")
    conn.execute("UPDATE PartOperations SET private_stage_note=' hidden original ',created_at='2000-01-01 00:00:00'")
    conn.execute("""INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,setup_hours,unit_hours)
        VALUES ('STAGE-API-OLD','PROC-B',10,'original batch operation','internal',7.5,8.25)""")
    key = conn.execute("SELECT id FROM BatchOperations WHERE op_code='STAGE-API-OLD'").fetchone()[0]
    conn.execute("INSERT INTO Schedule(op_id,start_time,end_time) VALUES (?,?,?)",
                 (key, "2026-10-01 08:00:00", "2026-10-01 09:00:00"))
    conn.commit()


def seed_stage_scale(conn, code, count, *, confirmed_route=True):
    conn.execute("INSERT INTO Parts(part_no,part_name,route_raw,route_parsed) VALUES (?,?,?,'yes')",
                 (code, "Stage scale " + str(count), "existing route"))
    conn.executemany("""INSERT INTO PartOperations(part_no,seq,op_type_name,op_type_id,source,setup_hours,unit_hours)
        VALUES (?,?,'Turning','PROC-IN','internal',0,1)""", [(code, seq) for seq in range(1, count + 1)])
    conn.commit()
    if confirmed_route:
        with TransactionManager(conn).transaction(begin_immediate=True):
            record_confirmation(conn, code, "route")


@pytest.fixture(name="stage_api")
def stage_api_fixture(app_client):
    api = StageAPI(app_client)
    with api.database() as conn:
        seed_process(conn)
        seed_history(conn)
    return api


def success(response):
    body = response.get_json()
    assert response.status_code == 200, body
    assert body["ok"] is True, body
    return body


def rejected(response, code, status=409, *, committed=False):
    body = response.get_json()
    assert response.status_code == status, body
    assert body["ok"] is False and body["committed"] == committed, body
    assert body["error"]["code"] == code, body
    assert response.headers["Cache-Control"] == "no-store"
    return body


class StageAPI:
    def __init__(self, client):
        self.client = client

    @contextmanager
    def database(self):
        conn = sqlite3.connect(self.client.application.config["DATABASE_PATH"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def ref(self, kind="part", code=PART):
        with self.database() as conn:
            return ref_for(conn, kind, code)

    def execute(self, sql, params=()):
        with self.database() as conn:
            conn.execute(sql, params)

    def rows(self, table, where="1=1", params=()):
        with self.database() as conn:
            return [dict(row) for row in conn.execute('SELECT * FROM "' + table + '" WHERE ' + where + " ORDER BY rowid", params)]

    def snapshot(self):
        with self.database() as conn:
            return all_table_snapshot(conn)

    def preserved(self):
        return {name: rows for name, rows in self.snapshot()[1].items() if name not in METADATA}

    def detail(self, code=PART):
        response = self.client.get(BASE + "/entities/part/" + self.ref(code=code))
        body = success(response)
        assert response.headers["Cache-Control"] == "no-store"
        assert body["meta"]["source"] == "production"
        return body

    def post(self, endpoint, body, code=PART):
        return self.client.post(BASE + "/process/" + self.ref(code=code) + "/" + endpoint, json=body)

    def route(self, code=PART):
        return {"mode": "text", "route_raw": self.rows("Parts", "part_no=?", (code,))[0]["route_raw"]}

    def source(self, code=PART):
        return {"operations": [{"ref": row["ref"], "source": row["source"], "op_type_ref": row["op_type_ref"],
                                "supplier_ref": row["supplier_ref"], "confirmed": True}
                               for row in self.detail(code)["data"]["operations"] if row["status"] == "active"],
                "discard_group_refs": []}

    def hours(self, code=PART):
        entity = self.detail(code)["data"]
        active = [row for row in entity["operations"] if row["status"] == "active"]
        groups = {row["external_group_ref"] for row in active}
        return {"operations": [{"ref": row["ref"], **({"setup_hours": row["setup_hours"], "unit_hours": row["unit_hours"]}
                  if row["source"] == "internal" else {"external_days": row["external_days"]})} for row in active],
                "groups": [{"ref": row["ref"], "total_days": row["total_days"]} for row in entity["external_groups"]
                           if row["ref"] in groups and row["merge_mode"] == "merged"], "confirm_zero_unit_hours": True}

    def preview(self, action, payload, code=PART):
        detail = self.detail(code)
        if action == "route_confirm":
            body = {**payload["route"], "snapshot_ref": detail["meta"]["snapshot_ref"]}
            return self.post("route-preview", body, code)
        return self.post("stage-preview", {"action": action, "input": payload,
                                          "snapshot_ref": detail["meta"]["snapshot_ref"]}, code)

    def context(self, action, payload, code=PART):
        if action == "hours_confirm":
            return self.detail(code)["data"]["write_context"]
        return success(self.preview(action, payload, code))["data"]["write_context"]

    def body(self, action, payload, code=PART, key=None):
        return {"request_key": key or "stage-api-" + uuid.uuid4().hex,
                "write_token": self.context(action, payload, code)["write_token"], "input": payload}

    def confirm(self, action, payload, code=PART):
        return success(self.post(action, self.body(action, payload, code), code))

    def prepare(self, stage="hours", code=PART):
        self.confirm("route_confirm", {"route": self.route(code), "discard_group_refs": []}, code)
        if stage == "hours":
            self.confirm("source_confirm", self.source(code), code)

    def intent(self, action):
        if action != "route_confirm":
            self.prepare("source" if action == "source_confirm" else "hours")
        payload = {"route_confirm": lambda: {"route": self.route(), "discard_group_refs": []},
                   "source_confirm": self.source, "hours_confirm": self.hours}[action]()
        return self.body(action, payload)

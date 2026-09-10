"""DB-owned helpers using real CQ adoption and file SQLite, never production."""

import sqlite3

from flask import Blueprint, g

from core.infrastructure.database import get_connection
from core.services.workbench.trial_adoption_history import WorkbenchTrialAdoptionHistoryService
from tests.workbench.trial_adoption_support import INTENT, preview, saved_scenario, service
from tests.workbench.trial_support import connect
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401
from web.routes.workbench.trial_adoption_history import register_trial_adoption_history_routes


def adopt(case, saved, key="db-history-adopt-0001"):
    return service(case.conn).adopt(saved["scenario_ref"], preview(case, saved), key, INTENT)


def seeded(case):
    saved = saved_scenario(case, suffix="db01")
    return saved, adopt(case, saved)


def advance(case, suffix="db02"):
    version = case.conn.execute("SELECT MAX(version) FROM ScheduleHistory").fetchone()[0]
    saved = saved_scenario(case, {"base": {"plan_ref": case.plan_ref(version)}}, changed=False, suffix=suffix)
    return saved, adopt(case, saved, "db-history-adopt-" + suffix)


def read(case, saved, **kwargs):
    return WorkbenchTrialAdoptionHistoryService(case.conn).read(saved["scenario_ref"], **kwargs)


def api(case, production_connection=True):
    bp = Blueprint("db_history", __name__)
    register_trial_adoption_history_routes(bp)
    case.app.register_blueprint(bp)

    @case.app.before_request
    def bind_history():
        g.db = get_connection(str(case.path)) if production_connection else connect(case.path)

    @case.app.teardown_request
    def close_history(_error):
        g.db.close()

    return case.app.test_client()


def raw_receipt(conn, saved, *, key, plan=None):
    """Fault/scale fixture only, not evidence of a successful adoption command."""
    import json
    import uuid
    row = dict(conn.execute("SELECT * FROM WorkbenchCommandReceipts WHERE action='trial.scenario.adopt' AND context_ref=?", (saved["scenario_ref"],)).fetchone())
    value = json.loads(row["outcome_json"])
    if plan:
        value["data"]["official_plan"].update(plan)
    conn.execute("INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_hash,outcome_json) VALUES (?,?,?,?,?,?)",
                 (key, uuid.uuid4().hex, row["action"], row["context_ref"], row["input_hash"], json.dumps(value)))
    conn.commit()


def deny_writes(conn):
    denied = []
    actions = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE,
               sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_ALTER_TABLE}

    def authorizer(action, first, second, _db, _source):
        if action in actions:
            denied.append((action, first, second))
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    conn.set_authorizer(authorizer)
    return denied

"""Observe the first ScheduleConfig mutation in the private test process."""

import hashlib
import json
import os
import re
import sqlite3
import threading
import traceback
from contextlib import closing
from datetime import datetime, timezone


def trace_schedule_config(root):
    original = sqlite3.connect
    lock = threading.Lock()
    evidence = {"pid": os.getpid(), "attempted_writes": 0, "requests": [], "completed": False}
    requests = {}
    mutation = re.compile(r"^\s*(?:INSERT(?:\s+OR\s+\w+)?\s+INTO|UPDATE|DELETE\s+FROM)\s+[\"`\[]?ScheduleConfig\b", re.I)

    def request_scope():
        from flask import has_request_context, request

        if not has_request_context():
            return None
        payload = request.get_json(silent=True)
        payload = payload if isinstance(payload, dict) else {}
        return {"method": request.method, "path": request.path, "request_key": payload.get("request_key")}

    def config_state():
        database = (root / "db/aps-live.db").resolve()
        database.relative_to(root.resolve())
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            rows = [dict(row) for row in conn.execute("SELECT * FROM ScheduleConfig ORDER BY id")]
        return {"rows": len(rows), "sha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()}

    def trace(statement):
        if not mutation.match(statement):
            return
        scope = request_scope()
        key = json.dumps(scope, sort_keys=True)
        with lock:
            evidence["attempted_writes"] += 1
            if key not in requests:
                requests[key] = {"request": scope, "attempted_writes": 0}
                evidence["requests"].append(requests[key])
            requests[key]["attempted_writes"] += 1
            if "first" in evidence:
                return
            evidence["first"] = None
        frames = [{"path": frame.filename, "line": frame.lineno, "function": frame.name}
                  for frame in traceback.extract_stack(limit=48)]
        result = {"event": "first_schedule_config_mutation", "at": datetime.now(timezone.utc).isoformat(),
                  "statement_kind": statement.split(None, 1)[0], "stack": frames,
                  "request": scope,
                  "policy": "Observation only; SQL, data, commit and errors are unchanged; no statement values persisted"}
        evidence["first"] = result
        first_file = root / "final-master-first-schedule-config-write.json"
        if not first_file.exists():
            first_file.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def connect(database, *args, **kwargs):
        connection = original(database, *args, **kwargs)
        connection.set_trace_callback(trace)
        return connection

    sqlite3.connect = connect

    def attach(app):
        evidence["before_requests"] = config_state()

        @app.after_request
        def observe_response(response):
            key = json.dumps(request_scope(), sort_keys=True)
            if key in requests:
                requests[key]["response_status"] = response.status_code
                requests[key]["committed_config"] = config_state()
            return response

    def finish():
        evidence["completed"] = True
        evidence["finished"] = datetime.now(timezone.utc).isoformat()
        path = root / ("final-master-schedule-config-trace-" + str(os.getpid()) + ".json")
        path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {"attach": attach, "finish": finish}

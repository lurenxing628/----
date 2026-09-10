"""Persist only the missing D acceptance cases before the real host opens."""

import sqlite3
from contextlib import closing

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.final_planning_seed import seed as planning_seed
from tests.workbench.test_run_jobs_support import JobCase
from tests.workbench.test_run_jobs_support import service as run_service
from tests.workbench.trial_support import service as trial_service


def _scenario(case, base, suffix):
    service = trial_service(case.conn)
    intent = {"base": base}
    preview = service.preview_create(intent)
    created = service.create(intent, preview["write_context"]["write_token"], "d-required-create-" + suffix)
    assert created["ok"] is True
    draft = created["data"]
    saved = service.save(draft["draft_ref"], {"name": "D required " + suffix},
                         draft["write_context"]["write_token"], "d-required-save-" + suffix)
    assert saved["ok"] is True
    return saved["data"]


def seed(app, *, required_case, **options):
    if required_case not in ("readonly", "stale"):
        raise ValueError("Unknown D required-case fixture")
    result = planning_seed(app, required_conflict=required_case == "readonly", **options)
    with closing(sqlite3.connect(app.config["DATABASE_PATH"])) as conn, app.app_context():
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        case = JobCase(conn)
        accepted = case.accept(key="d-required-run-" + required_case, settings=case.settings("B1", "B2"))
        if required_case == "readonly":
            original = conn.execute("SELECT name FROM Machines WHERE machine_id='M1'").fetchone()[0]
            conn.execute("UPDATE Machines SET name=? WHERE machine_id='M1'", (original + " after admission",))
            conn.commit()
            try:
                WorkbenchRunWorker(conn).execute(accepted["run_ref"])
            except WorkbenchCommandRejected as error:
                assert error.code == "snapshot_stale"
            else:
                raise AssertionError("Actual worker must persist the fact-drift failure")
            failed = run_service(conn).get(accepted["run_ref"])
            assert failed["state"] == "failed" and failed["candidates"] == []
            assert failed["result_persisted"] is False
            conn.execute("UPDATE Machines SET name=? WHERE machine_id='M1'", (original,))
            conn.commit()
            base = {"plan_ref": result["original_plan_ref"]}
        else:
            completed = WorkbenchRunWorker(conn).execute(accepted["run_ref"])
            assert completed["state"] == "complete" and completed["result_persisted"] is True
            assert all(row["task_count"] == result["task_count"] for row in completed["candidates"])
            base = {"candidate_ref": completed["candidates"][0]["candidate_ref"]}
        saved = _scenario(case, base, required_case)
        result["required"] = {"case": required_case, "run_ref": accepted["run_ref"],
                              "scenario_ref": saved["scenario_ref"], "draft_ref": saved["draft_ref"],
                              "baseline": saved["baseline"], "task_count": saved["task_count"],
                              "seed_path": __file__, "synthetic_business_responses": False}
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    return result

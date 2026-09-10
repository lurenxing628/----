"""EE-owned real engine/SQLite fixtures and isolated existing HTTP routes."""

from contextlib import contextmanager
from threading import Thread

from flask import Blueprint, Flask, g, send_from_directory
from werkzeug.serving import make_server

from tests.workbench.ea_zero_duration_support import adopt, trial_adoption_service
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_support import compute
from tests.workbench.trial_support import change, connect, create, service
from web.routes.workbench.plan_reads import register_plan_read_routes
from web.routes.workbench.run_candidates import register_run_candidate_routes
from web.routes.workbench.trial import register_trial_routes


def seed(case, mixed):
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0,op_type_name='Point 00'")
    batches = ["B1"]
    for index in range(1, 12):
        batch = f"POINT-{index:02d}"
        case.batch(batch)
        batches.append(batch)
        case.operation(batch=batch, setup_hours=0, unit_hours=0, op_type_name=f"Point {index:02d}")
    if mixed:
        case.batch("NORMAL")
        batches.append("NORMAL")
        for index in range(1, 101):
            case.operation(batch="NORMAL", seq=index, setup_hours=0, unit_hours=1 / 3600,
                           op_type_name=f"Normal {index:03d}")
    case.conn.commit()
    run, refs = compute(case, case.settings(*batches))
    assert refs, "Real engine must finish and persist candidate rows"
    plan = adopt(case, refs[0], key="ee-point-first-adopt-01")
    draft = create(case, {"base": {"plan_ref": plan["plan_ref"]}}, key="ee-point-draft-create-01")
    for index in (1, 2):
        task = next(i for i, row in enumerate(draft["tasks"]) if row["process_label"] == f"Point {index:02d}")
        draft = change(case, draft, task=task, start="2026-09-09T08:00:0" + str(index),
                       machine="M1", operator="O1", key="ee-point-change-000" + str(index))["data"]
    saved = service(case.conn).save(draft["draft_ref"], {"name": "EE point source"},
                                   draft["write_context"]["write_token"], "ee-point-scenario-save")["data"]
    adoption = trial_adoption_service(case.conn)
    preview = adoption.preview(saved["scenario_ref"])
    assert preview["validation"]["can_adopt"], preview
    outcome = adoption.adopt(saved["scenario_ref"], preview["write_context"]["write_token"], "ee-point-trial-adopt", INTENT)
    assert outcome["ok"], outcome
    second = outcome["data"]["official_plan"]
    editing = create(case, {"base": {"plan_ref": second["plan_ref"]}}, key="ee-point-browser-draft")
    return {"run_ref": run, "candidate_ref": refs[0], "plan_ref": second["plan_ref"], "initial_plan_ref": plan["plan_ref"],
            "draft_ref": editing["draft_ref"], "scenario_ref": saved["scenario_ref"], "mixed": mixed}


def app_for(case, output):
    app = Flask("ee-point-components", static_folder=None)
    app.config["TESTING"] = True
    bp = Blueprint("ee_point_routes", __name__)
    register_plan_read_routes(bp)
    register_run_candidate_routes(bp)
    register_trial_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def bind():
        g.db = connect(case.path)

    @app.teardown_request
    def close(error):
        g.db.close()

    @app.route("/")
    def index():
        return send_from_directory(str(output), "index.html")

    @app.route("/assets/<path:name>")
    def assets(name):
        return send_from_directory(str(output), name)

    return app


@contextmanager
def serve(app):
    server = make_server("127.0.0.1", 0, app, threaded=True)
    assert server.server_port not in (52392, 58448, 64612)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        assert not thread.is_alive()

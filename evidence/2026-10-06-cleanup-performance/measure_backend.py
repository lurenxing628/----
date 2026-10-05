"""Fixed-workload old/current APS measurement on disposable databases only."""

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("seed", "measure"))
    parser.add_argument("--repo", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--batches", type=int, required=True)
    parser.add_argument("--operations", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dispatch", choices=("sgs",))
    args = parser.parse_args()
    repo, db = Path(args.repo).resolve(), Path(args.db).resolve()
    sys.path.insert(0, str(repo))
    os.chdir(str(repo))
    for key, value in {
        "APS_DB_PATH": str(db),
        "APS_LOG_DIR": str(db.parent / "logs"),
        "APS_BACKUP_DIR": str(db.parent / "backups"),
        "APS_EXCEL_TEMPLATE_DIR": str(db.parent / "templates"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }.items():
        os.environ[key] = value

    def connect():
        result = sqlite3.connect(str(db), timeout=30)
        result.row_factory = sqlite3.Row
        result.execute("PRAGMA foreign_keys=ON")
        return result

    if args.mode == "seed":
        from core.infrastructure.database import ensure_schema
        from core.services.scheduler.config.config_field_spec import default_snapshot_values
        from tests.workbench.run_jobs_support import JobCase

        db.parent.mkdir(parents=True, exist_ok=True)
        ensure_schema(str(db), schema_path=str(repo / "schema.sql"), backup_dir=None)
        conn = connect()
        conn.execute(
            "INSERT INTO WorkbenchCalendarDefaults(singleton,periods_json) VALUES (1,?)",
            ('[{"start":"08:00","end":"16:00","day_offset":0}]',),
        )
        conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('T1','Turning','internal')")
        for i in range(1, 51):
            conn.execute(
                "INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?, 'T1')", ("M" + str(i), "Lathe " + str(i))
            )
            conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", ("O" + str(i), "Operator " + str(i)))
            conn.execute(
                "INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", ("O" + str(i), "M" + str(i))
            )
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Benchmark part')")
        for i in range(1, 31):
            conn.execute(
                "INSERT INTO Parts(part_no,part_name) VALUES (?,?)", ("P" + str(i + 1), "Catalog part " + str(i))
            )
        for i in range(1, 51):
            conn.execute(
                "INSERT INTO Materials(material_id,name,unit,stock_qty) VALUES (?,?,?,?)",
                ("MAT-" + str(i).zfill(3), "Benchmark material " + str(i), "piece", 100),
            )
        for seq in range(1, args.operations + 1):
            conn.execute(
                "INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,unit_hours) VALUES ('P1',?,'T1','Turning','internal',0.04)",
                (seq,),
            )
        for key, value in default_snapshot_values().items():
            conn.execute(
                "INSERT OR REPLACE INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value))
            )
        for key, value in {
            "auto_backup_enabled": "no",
            "auto_backup_cleanup_enabled": "no",
            "auto_log_cleanup_enabled": "no",
            "auto_backup_interval_minutes": "60",
            "auto_backup_keep_days": "7",
            "auto_backup_cleanup_interval_minutes": "60",
            "auto_log_cleanup_keep_days": "30",
            "auto_log_cleanup_interval_minutes": "60",
        }.items():
            conn.execute("INSERT OR REPLACE INTO SystemConfig(config_key,config_value) VALUES (?,?)", (key, value))
        case = JobCase(conn)
        for batch in range(args.batches):
            code = "B" + str(batch + 1).zfill(4)
            case.batch(code)
            resource = str(batch % 10 + 1)
            for seq in range(1, args.operations + 1):
                case.operation(
                    batch=code, seq=seq, unit_hours=0.04, machine_id="M" + resource, operator_id="O" + resource
                )
        options = dict(
            algo_mode="greedy",
            graph_candidate_weight_count=3,
            time_budget_seconds=60,
            ortools_enabled="no",
            freeze_window_enabled="no",
        )
        if args.dispatch:
            options["dispatch_mode"] = args.dispatch
        case.config(**options)
        conn.close()
        Path(args.output).write_text(json.dumps({"seeded": True, "tasks": args.batches * args.operations}) + "\n")
        sys.exit(0)

    samples = {}

    def timed(name, fn):
        started = time.perf_counter()
        result = fn()
        samples[name] = (time.perf_counter() - started) * 1000
        return result

    started = time.perf_counter()
    from web.bootstrap import factory

    app = factory.create_app_core(
        ui_mode="default", enable_secret_key=False, enable_security_headers=False, enable_session_cookie_hardening=False
    )
    assert Path(app.config["DATABASE_PATH"]).resolve() == db
    samples["backend_startup_ms"] = (time.perf_counter() - started) * 1000
    # Helper imports are outside the measured business phases, on both versions.
    from core.models.workbench_process_query import ProcessPageRequest
    from core.models.workbench_report import ReportPage, ReportScope
    from core.models.workbench_resource_query import ResourcePageRequest
    from core.services.workbench.facts.candidate_store import CandidateStore
    from core.services.workbench.process.queries import WorkbenchProcessQueryService
    from core.services.workbench.report.facts import WorkbenchReportFacts
    from core.services.workbench.report.queries import report_workspace
    from core.services.workbench.resource.queries import WorkbenchResourceQueryService
    from core.services.workbench.run.worker import WorkbenchRunWorker
    from tests.workbench.run_candidate_adoption_support import INTENT
    from tests.workbench.run_candidate_adoption_support import service as adoption_service
    from tests.workbench.run_jobs_support import JobCase
    from tests.workbench.run_jobs_support import service as run_service
    from tests.workbench.trial_support import service as trial_service

    conn = connect()
    case = JobCase(conn)
    case.path = db
    codes = ["B" + str(i + 1).zfill(4) for i in range(args.batches)]
    settings = case.settings(*codes)
    with app.app_context():

        def resources():
            reader = WorkbenchResourceQueryService(conn, "machine")
            with reader.read_snapshot():
                rows, page = reader.page(ResourcePageRequest("machine", size=20))
                assert len(rows) == 20 and page["total"] == 50
            return len(rows)

        timed("resource_list_ms", resources)

        def processes():
            reader = WorkbenchProcessQueryService(conn)
            with reader.read_snapshot():
                result = reader.page(ProcessPageRequest(size=20))
                assert result["page"]["total"] == 31
            return result["page"]["total"]

        timed("process_list_ms", processes)
        ref = timed("preflight_ms", lambda: case.preflight(settings))
        run = run_service(conn)
        preview = timed("run_preview_ms", lambda: run.preview(ref))
        accepted = timed(
            "run_accept_ms", lambda: run.accept(ref, preview["write_context"]["write_token"], "perf-run-request-000001")
        )
        generated = timed("generate_candidates_ms", lambda: WorkbenchRunWorker(conn).execute(accepted["run_ref"]))
        assert generated["state"] == "complete", generated
        candidate_refs = [row["candidate_ref"] for row in generated["candidates"]]
        assert len(candidate_refs) == 4, (len(candidate_refs), generated)
        candidate = candidate_refs[0]

        def candidate_rows():
            with CandidateStore(conn).snapshot():
                rows = CandidateStore(conn).tasks(candidate)
                assert len(rows) == args.batches * args.operations
            return rows

        rows = timed("candidate_read_ms", candidate_rows)
        arrangement = sorted(
            [
                [
                    row["payload"][key]
                    for key in ("op_id", "machine_id", "operator_id", "start_time", "end_time", "source")
                ]
                for row in rows
            ]
        )
        trial = trial_service(conn)
        intent = {"base": {"candidate_ref": candidate}}
        trial_preview = timed("trial_preview_ms", lambda: trial.preview_create(intent))
        created = timed(
            "trial_create_ms",
            lambda: trial.create(intent, trial_preview["write_context"]["write_token"], "perf-trial-create-000001"),
        )
        assert created["ok"], created
        draft = created["data"]
        saved = timed(
            "trial_save_ms",
            lambda: trial.save(
                draft["draft_ref"],
                {"name": "Fixed benchmark"},
                draft["write_context"]["write_token"],
                "perf-trial-save-000001",
            ),
        )
        assert saved["ok"], saved
        scenario = timed("trial_reopen_ms", lambda: trial.scenario(saved["data"]["scenario_ref"]))
        assert len(scenario["tasks"]) == args.batches * args.operations
        adopting = adoption_service(conn)
        adoption_preview = timed("adopt_preview_ms", lambda: adopting.preview(candidate))
        assert adoption_preview["validation"]["can_adopt"], adoption_preview
        adopted = timed(
            "adopt_commit_ms",
            lambda: adopting.adopt(
                candidate, adoption_preview["write_context"]["write_token"], "perf-adopt-request-000001", INTENT
            ),
        )
        assert adopted["ok"], adopted
        version = conn.execute("SELECT MAX(version) FROM ScheduleHistory").fetchone()[0]
        plan_ref = case.plan_ref(version)
        now = datetime(2026, 9, 30, 12)

        def report():
            reader = WorkbenchReportFacts(conn)
            with reader.read_snapshot():
                facts = reader.read(ReportScope(plan_ref=plan_ref), as_of=now)
                data, ordered, labels = report_workspace(
                    reader, facts, {"as_of": now.isoformat()}, "delivery", ReportPage()
                )
            assert len(ordered) == args.batches * args.operations
            return {"rows": len(ordered), "summary": data["summary"]}

        report_result = timed("report_read_ms", report)
        page_count = conn.execute("PRAGMA page_count").fetchone()[0]
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        artifact_bytes = conn.execute(
            "SELECT SUM(LENGTH(CAST(artifact_json AS BLOB))) FROM WorkbenchRunCandidates"
        ).fetchone()[0]
        snapshot_bytes = conn.execute(
            "SELECT SUM(LENGTH(CAST(snapshot_json AS BLOB))) FROM WorkbenchTrialScenarios"
        ).fetchone()[0]
        traces = [
            json.loads(row[0])
            for row in conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates ORDER BY sequence")
        ]
        search_counts = [
            {
                key: trace.get("search_report", {}).get(key)
                for key in ("decoder_invocations", "evaluated_candidates", "iterations", "stop_reason")
            }
            for trace in traces
        ]
        output = {
            "search_counts": search_counts,
            "status": "passed",
            "timings_ms": samples,
            "business_chain_ms": sum(v for k, v in samples.items() if k != "backend_startup_ms"),
            "total_startup_and_business_ms": sum(samples.values()),
            "task_count": len(rows),
            "candidate_count": len(candidate_refs),
            "arrangement": arrangement,
            "report": report_result,
            "plan_ref": plan_ref,
            "run_ref": accepted["run_ref"],
            "candidate_ref": candidate,
            "storage": {
                "database_pages_bytes": page_count * page_size,
                "candidate_artifact_bytes": artifact_bytes,
                "trial_snapshot_bytes": snapshot_bytes,
            },
            "db": str(db),
            "repo": str(repo),
        }
    conn.close()
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "passed", "timings_ms": samples, "business_chain_ms": output["business_chain_ms"]}))


if __name__ == "__main__":
    main()

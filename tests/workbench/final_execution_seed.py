"""Deterministic business facts on a current factory-created temporary database."""

from contextlib import closing
from pathlib import Path

from core.infrastructure.database import get_connection
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository
from tests.workbench.calibration_adoption_host_support import prepare_calibration
from tests.workbench.execution_ledger_support import LedgerCase
from tests.workbench.final_execution_chain_seed import chain_plan
from tests.workbench.final_execution_resources_seed import resource_groups
from tests.workbench.report_execution_ledger_support import report_ledger_api
from tests.workbench.reports_review_browser_seed import seed as report_seed
from tests.workbench.run_jobs_support import JobCase


class CalibrationSeedJob(JobCase):
    path: Path


def seed(app, profile, root):
    api = report_ledger_api.__wrapped__(app.test_client())
    if profile == "chain":
        result = chain_plan(api)
    elif profile == "resources":
        result = resource_groups(api)
    elif profile == "reports":
        result = report_seed(api)
    elif profile == "execution":
        result = execution(api)
    else:
        with api.db() as conn:
            job = CalibrationSeedJob(conn)
            job.path = Path(app.config["DATABASE_PATH"])
            # The API fixture already owns version 1; samples use the next version.
            from tests.workbench.template_lineage_support import completed

            conn.execute("DELETE FROM Schedule WHERE version=1")
            conn.execute("DELETE FROM ScheduleHistory WHERE version=1")
            conn.commit()
            case = prepare_calibration(job)
            ids = [row[0] for row in conn.execute("SELECT id FROM BatchOperations WHERE batch_id LIKE 'HOST-%' AND seq=1 ORDER BY batch_id")]
            assert len(ids) == 5
            outlier = case.ledger.get_task(case.task(1, ids[-1])).reports[0]
            case.command("correct", outlier.report_ref, {
                "original_revision_ref": outlier.revision_ref, "reason": "保留真实离群样本检验中位数",
                "actual_start": "2026-08-10T08:00:00", "effective_processing_hours": 500})
            template_id = conn.execute("SELECT id FROM PartOperations WHERE part_no='P1' AND seq=1").fetchone()[0]
            template_ref = WorkbenchTemplateLineageRepository(conn).template(template_id)["template_operation_ref"]
            reports = [report.to_dict() for op in ids for report in case.ledger.get_task(case.task(1, op)).reports]
            result = {"template_ref": template_ref, "part_ref": case.ref("part", "P1"),
                      "sample_reports": reports, "sample_operation_ids": ids,
                      "method_expected_median": 3, "sample_count": 5,
                      "seed_method": completed.__module__ + ".completed"}
    with closing(get_connection(app.config["DATABASE_PATH"])) as conn:
        conn.executemany("INSERT OR REPLACE INTO SystemConfig(config_key,config_value) VALUES (?, 'no')",
                         [(key,) for key in ("auto_backup_enabled", "auto_backup_cleanup_enabled", "auto_log_cleanup_enabled")])
        conn.commit()
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    return {"domain": profile, "final_e": result, "root": str(root)}


def execution(api):
    with api.db() as conn:
        case = LedgerCase(conn)
        ids = [1] + [case.op("FINAL-E-" + str(index), seq=index) for index in range(2, 31)]
        pieces = [case.op("FINAL-E-PIECE-" + piece, piece=piece) for piece in ("分件甲", "分件乙", "0")]
        for op_id in ids[1:] + pieces:
            conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) "
                         "VALUES (1,?,'M1','O1','2026-09-09 08:00:00','2026-09-09 10:00:00')", (op_id,))
        conn.execute("UPDATE Machines SET name='中文车床' WHERE machine_id='M1'")
        conn.execute("UPDATE Operators SET name='中文人员' WHERE operator_id='O1'")
        conn.commit()
        case.event(ids[2], "start", time="2026-09-01T08:00:00")
        case.event(ids[2], "finish", time="2026-09-01T10:00:00")
        case.event(ids[4], "start", time="2026-09-01T08:00:00")
        case.event(ids[4], "pause", time="2026-09-01T09:00:00")
        first = case.command("create", case.task(1, ids[1]), {"actual_start": "2026-09-01T08:00:00"})
        for index in range(6):
            case.command("create", case.task(1, ids[3]), case.values(1,
                actual_start=f"2026-09-01T{index + 8:02d}:00:00",
                actual_end=f"2026-09-01T{index + 9:02d}:00:00", effective_processing_hours=.5))
        return {"operation_ids": ids, "piece_ids": pieces, "plan_ref": case.plan_ref(1),
                "task_refs": {str(op): case.task(1, op) for op in ids + pieces},
                "operation_refs": {str(op): case.ledger.repo.task(case.task(1, op))["operation_ref"] for op in ids + pieces},
                "original_report": first["data"]["rows"][0], "legacy_events": 4,
                "machine_ref": case.ref("machine", "M1"), "operator_ref": case.ref("operator", "O1")}

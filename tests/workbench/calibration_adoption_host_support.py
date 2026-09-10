"""Current-schema samples for managed entrypoint tests, with actual template copies."""

import sqlite3
from contextlib import closing

from core.services.scheduler.batch_service import BatchService
from core.services.workbench.production_report import WorkbenchProductionReportService
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository
from tests.workbench.calibration_adoption_support import snapshot
from tests.workbench.process_workflow_support import confirm_all
from tests.workbench.template_lineage_support import TemplateLineageCase, completed

BASE = "/api/workbench/v1/calibration/"
INTENT = {"reason": "Verified completed samples from the original template", "declared_operator": "Planner"}


def database_snapshot(path):
    with closing(sqlite3.connect(path)) as conn:
        return snapshot(conn)


def prepare_calibration(job_case):
    conn = job_case.conn
    conn.executemany("""INSERT INTO PartOperations
        (part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours)
        VALUES ('P1',?,'T1','Turning','internal',0,?)""", [(1, 1), (2, 7)])
    conn.execute("UPDATE Parts SET route_raw='Turning,Turning',route_parsed='yes' WHERE part_no='P1'")
    conn.commit()
    confirm_all(conn)
    case = TemplateLineageCase(conn)
    case.writer = WorkbenchProductionReportService(conn)
    case.batch_service = BatchService(conn)
    case.lineage_repo = WorkbenchTemplateLineageRepository(conn)
    case.template_id = conn.execute("SELECT id FROM PartOperations WHERE seq=1").fetchone()[0]
    case.template_ref = case.lineage_repo.template(case.template_id)["template_operation_ref"]
    case.db_path = str(job_case.path)
    case.ids, case.reports = completed(case, [1, 2, 3, 4, 5], prefix="HOST", version=1)
    return case


def preview_adoption(client, case, key):
    response = client.post(BASE + case.template_ref + "/adopt-preview", json={"input": INTENT})
    result = response.get_json()
    assert response.status_code == 200 and result["data"]["validation"]["can_adopt"], result
    assert result["data"]["suggestion"]["sample_count"] == 5
    assert result["data"]["suggestion"]["suggested_unit_hours"] == 3
    return {"write_token": result["data"]["write_context"]["write_token"], "request_key": key,
            "input": {**INTENT, "confirm": True}}

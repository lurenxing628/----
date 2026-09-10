"""R1-A private production DATE connections and the real managed worker."""

import json
from datetime import date

import pytest

from core.infrastructure.database import get_connection
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from core.services.workbench.run_jobs import WorkbenchRunService
from tests.workbench.ea_zero_duration_support import adoption_service, trial_adoption_service
from tests.workbench.test_piece_chain_support import piece_layout
from tests.workbench.test_run_candidate_adoption_support import INTENT, assert_retained
from tests.workbench.test_run_jobs_support import JobCase
from tests.workbench.trial_support import snapshot
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
from web.bootstrap.workbench_run_runtime import WorkbenchRunRuntime, install_workbench_run_runtime


class PointCase(JobCase):
    runtime: WorkbenchRunRuntime

    def __init__(self, original):
        super().__init__(get_connection(str(original.path)))
        self.path, self.op_id, self.app = original.path, original.op_id, original.app


@pytest.fixture
def point_case(trial_case, tmp_path):
    case = PointCase(trial_case)
    assert type(case.conn.execute("SELECT due_date FROM Batches").fetchone()[0]) is date
    case.app.config["DATABASE_PATH"] = str(case.path)
    runtime_dir = str(tmp_path / "r1a-private-runtime")
    ownership = acquire_runtime_lock(runtime_dir, db_path=str(case.path))
    runtime = install_workbench_run_runtime(case.app, runtime_lock=ownership)
    assert runtime.ready, runtime.status
    case.runtime = runtime
    try:
        yield case
    finally:
        assert runtime.shutdown(timeout=30), runtime.status
        release_runtime_lock(runtime_dir, db_path=str(case.path))
        case.conn.close()


def layout(case, *, mixed=True):
    ids = piece_layout(case, parallel=False, unit=.25 if mixed else 0)
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0 WHERE seq IN (20,40)")
    for piece in ("item-A", "item-B", "item-C"):
        ids[piece, 50] = case.operation(seq=50, piece_id=piece, op_code=piece + "-50", unit_hours=0)
    case.conn.execute("UPDATE Batches SET ready_date='2026-09-09' WHERE batch_id='B1'")
    case.conn.commit()
    return ids


def managed_run(case, *, key="r1a-managed-run-0001", settings=None):
    accepted = case.accept(key=key, settings=settings)
    case.runtime(accepted["run_ref"])
    assert case.runtime.wait_idle(timeout=30), case.runtime.status
    result = WorkbenchRunService(case.conn).get(accepted["run_ref"])
    return result


def candidate(case, **kwargs):
    result = managed_run(case, **kwargs)
    assert result["state"] == "complete", result
    assert result["result_persisted"], result
    return result["candidates"][0]["candidate_ref"]


def artifact(case, ref):
    return json.loads(case.conn.execute(
        "SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=?", (ref,)).fetchone()[0])


def adopt(case, ref, *, trial=False, key="r1a-adopt-candidate-0001"):
    svc = (trial_adoption_service if trial else adoption_service)(case.conn)
    preview = svc.preview(ref)
    assert preview["validation"]["can_adopt"], preview
    before = snapshot(case.conn)
    result = svc.adopt(ref, preview["write_context"]["write_token"], key, INTENT)
    assert result["ok"], result
    assert_retained(before, snapshot(case.conn))
    return result


def workspace(conn, plan_ref):
    reader = WorkbenchPlanQueryService(conn)
    with reader.read_snapshot():
        data, _ = reader.workspace(PlanReadScope(plan_ref))
    return data


def operation_ref(case, op_id):
    return case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs "
        "WHERE kind='operation' AND active=1 AND source_key=?", (str(op_id),)).fetchone()[0]

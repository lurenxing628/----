"""EA backend integration factories; the HTTP point surface remains disabled."""

from core.services.workbench.run_candidate_adoption import WorkbenchRunCandidateAdoptionService
from core.services.workbench.trial_adoption import WorkbenchTrialAdoptionService
from tests.workbench.test_run_candidate_adoption_support import INTENT
from tests.workbench.test_run_candidate_support import compute
from web.routes.workbench.write_context import issue_write_context, validate_write_context


def adoption_service(conn):
    return WorkbenchRunCandidateAdoptionService(conn, integration_enabled=True, point_rendering_enabled=True,
        context_factory=issue_write_context, context_validator=validate_write_context)


def trial_adoption_service(conn):
    return WorkbenchTrialAdoptionService(conn, integration_enabled=True, point_rendering_enabled=True,
        context_factory=issue_write_context, context_validator=validate_write_context)


def point_candidate(case, *, setup=0, unit=0, quantity=3, settings=None):
    case.conn.execute("UPDATE BatchOperations SET setup_hours=?,unit_hours=? WHERE id=?", (setup, unit, case.op_id))
    case.conn.execute("UPDATE Batches SET quantity=? WHERE batch_id='B1'", (quantity,))
    case.conn.commit()
    return compute(case, settings)[1][0]


def adopt(case, ref, key="ea-adopt-point-0001"):
    svc = adoption_service(case.conn)
    preview = svc.preview(ref)
    assert preview["validation"]["can_adopt"], preview
    result = svc.adopt(ref, preview["write_context"]["write_token"], key, INTENT)
    assert result["ok"], result
    return result["data"]["official_plan"]

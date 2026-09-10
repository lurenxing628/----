"""Recheck split work before issuing a run token and inside run acceptance."""

from core.errors import AppError
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError

from .run_input import prepare_candidate_run_input
from .run_jobs_facts import run_execution_projections


def piece_admission_issues(conn, settings):
    selected = set(settings["batch_refs"])
    rows = conn.execute("SELECT r.ref FROM BatchOperations bo JOIN WorkbenchEntityRefs r "
        "ON r.kind='batch' AND r.entity_key=bo.batch_id AND r.active=1 WHERE bo.piece_id IS NOT NULL").fetchall()
    if not any(row[0] in selected for row in rows):
        return []
    try:
        prepare_candidate_run_input(conn, settings, run_execution_projections(conn, settings))
    except (CandidateRunInputError, CandidateAdoptionBlocked) as exc:
        return [{"code": exc.code, "message": str(exc)}]
    except AppError as exc:
        return [{"code": (exc.details or {}).get("reason", "piece_input_unproven"), "message": str(exc)}]
    return []

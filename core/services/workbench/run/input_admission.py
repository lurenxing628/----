"""Use the worker's read-only input preparation before run authorization."""

from core.errors import AppError
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError

from .input import prepare_candidate_run_input
from .jobs_facts import run_execution_projections


def candidate_admission_issues(conn, settings):
    try:
        prepare_candidate_run_input(conn, settings, run_execution_projections(conn, settings), capture_fingerprint=False)
    except (CandidateRunInputError, CandidateAdoptionBlocked) as exc:
        return [{"code": exc.code, "message": str(exc)}]
    except AppError as exc:
        return [{"code": (exc.details or {}).get("reason", "candidate_input_unproven"), "message": exc.message}]
    return []

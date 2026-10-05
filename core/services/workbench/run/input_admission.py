"""Recheck split work before issuing a run token and inside run acceptance."""

from core.errors import AppError
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError
from data.repositories.workbench_run_facts_repo import WorkbenchRunFactsRepository

from .input import prepare_candidate_run_input
from .jobs_facts import run_execution_projections


def piece_admission_issues(conn, settings):
    selected = set(settings["batch_refs"])
    refs = WorkbenchRunFactsRepository(conn).piece_batch_refs()
    if not any(ref in selected for ref in refs):
        return []
    try:
        prepare_candidate_run_input(conn, settings, run_execution_projections(conn, settings), capture_fingerprint=False)
    except (CandidateRunInputError, CandidateAdoptionBlocked) as exc:
        return [{"code": exc.code, "message": str(exc)}]
    except AppError as exc:
        return [{"code": (exc.details or {}).get("reason", "piece_input_unproven"), "message": exc.message}]
    return []

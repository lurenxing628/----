"""Use the worker's read-only input preparation before run authorization."""

from core.errors import AppError
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError

from .jobs_facts import run_baseline, run_execution_projections


def candidate_admission_issues(conn, *, prepared):
    from .input import prepare_candidate_run_input

    settings = prepared.settings
    try:
        if prepared.config_error is not None:
            raise prepared.config_error.with_traceback(None)
        prepared.execution_projections = run_execution_projections(
            conn,
            settings,
            capture=prepared.capture,
            existing=list(prepared.preflight_facts.execution_projections.values()),
            service=prepared.preflight_facts.execution_service,
        )
        prepared.baseline = run_baseline(capture=prepared.capture)
        result = prepare_candidate_run_input(
            conn,
            settings,
            prepared.execution_projections,
            facts=prepared.preflight_facts,
            config_snapshot=prepared.config_snapshot,
            baseline=prepared.baseline,
            held=prepared.held_arrangements,
        )
        prepared.prepared_input = result
    except (CandidateRunInputError, CandidateAdoptionBlocked) as exc:
        return [{"code": exc.code, "message": str(exc)}]
    except AppError as exc:
        return [{"code": (exc.details or {}).get("reason", "candidate_input_unproven"), "message": exc.message}]
    return []

"""Use the worker's read-only input preparation before run authorization."""

from core.errors import AppError
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError

from .jobs_facts import run_baseline, run_execution_projections


def candidate_admission_issues(conn, settings, *, prepared):
    from .input import prepare_candidate_run_input

    try:
        if prepared.config_error is not None:
            raise prepared.config_error
        prepared.execution_projections = run_execution_projections(conn, settings, capture=prepared.capture,
            existing=prepared.execution_projections, service=getattr(prepared.preflight_facts, "execution_service", None))
        prepared.baseline = run_baseline(conn, capture=prepared.capture)
        result = prepare_candidate_run_input(conn, settings, prepared.execution_projections,
            capture_fingerprint=False, facts=prepared.preflight_facts, config_snapshot=prepared.config_snapshot,
            baseline=prepared.baseline,
            validated_projections={row.operation_ref: row for row in prepared.execution_projections})
        prepared.prepared_input = result
    except (CandidateRunInputError, CandidateAdoptionBlocked) as exc:
        return None, [{"code": exc.code, "message": str(exc)}]
    except AppError as exc:
        return None, [{"code": (exc.details or {}).get("reason", "candidate_input_unproven"), "message": exc.message}]
    return result, []

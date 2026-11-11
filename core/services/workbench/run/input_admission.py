"""Use the worker's read-only input preparation before run authorization."""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

from core.errors import AppError
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError

from .input import PreparedBusinessInput, prepare_business_input
from .jobs_facts import run_baseline, run_execution_projections
from .preflight import PreparedPreflight


@dataclass(frozen=True)
class PreparedAdmission:
    preflight: PreparedPreflight
    baseline: Optional[Dict[str, Any]]
    execution_projections: Sequence[Any]
    business_input: Optional[PreparedBusinessInput]
    issues: Tuple[Dict[str, Any], ...]


def prepare_candidate_admission(conn, *, prepared: PreparedPreflight) -> PreparedAdmission:
    settings = prepared.settings
    baseline: Optional[Dict[str, Any]] = None
    projections: Sequence[Any] = prepared.execution_projections
    try:
        if prepared.config_error is not None:
            raise prepared.config_error.with_traceback(None)
        baseline = run_baseline(capture=prepared.capture)
        latest_plan_rows = prepared.preflight_facts.latest_plan_rows(baseline["version"] or 0)
        projections = tuple(
            run_execution_projections(
                settings,
                capture=prepared.capture,
                existing=tuple(prepared.preflight_facts.execution_projections.values()),
                ledger=prepared.preflight_facts.ledger,
                facts=prepared.preflight_facts,
                latest_plan_rows=latest_plan_rows,
            )
        )
        business_input = prepare_business_input(
            conn,
            settings,
            projections,
            facts=prepared.preflight_facts,
            config_snapshot=prepared.config_snapshot,
            baseline=baseline,
            held=prepared.held_arrangements,
            preflight_rows=prepared.evaluation_rows,
        )
    except (CandidateRunInputError, CandidateAdoptionBlocked) as exc:
        return PreparedAdmission(
            preflight=prepared,
            baseline=baseline,
            execution_projections=projections,
            business_input=None,
            issues=({"code": exc.code, "message": str(exc)},),
        )
    except AppError as exc:
        return PreparedAdmission(
            preflight=prepared,
            baseline=baseline,
            execution_projections=projections,
            business_input=None,
            issues=(
                {
                    "code": (exc.details or {}).get("reason", "candidate_input_unproven"),
                    "message": exc.message,
                },
            ),
        )
    return PreparedAdmission(
        preflight=prepared,
        baseline=baseline,
        execution_projections=projections,
        business_input=business_input,
        issues=(),
    )

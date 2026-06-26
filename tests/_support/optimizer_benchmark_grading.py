"""Grade the APS greedy scheduler against external benchmark optima.

Maturity: this is *offline scaffolding*, verified to run on real benchmark data
by its unit tests. It is NOT yet wired into the e2e proof-harness output
(``benchmark_optimizer_proof_harness.py``); it does not emit BenchmarkReference
payloads on the live path.

Tier-1 (objective-comparable on one component): SMTWT instances graded on
``overdue_count`` (number of tardy jobs, 1||sum U_j). This metric is
weight-independent, so it sidesteps the fact that APS only has 3 priority weight
classes while SMTWT uses free weights -- see
:mod:`tests._support.optimizer_benchmark_loaders`. The exact optimum comes from
Moore-Hodgson, so it measures, in the same model, how far greedy is from optimal
on the *primary* lexicographic component of ``min_overdue`` at n=40/50 scale that
the factorial tiny oracle cannot reach. It does NOT prove full ``min_overdue``
optimality: that objective is a lexicographic 5-tuple (overdue_count,
weighted_tardiness, total_tardiness, makespan, changeover); Moore-Hodgson only
pins the first entry and says nothing about the tie-breakers.

Exact time mapping (verified against ``due_exclusive`` = due-date 00:00 + 1 day):
a job with integer processing time ``p`` and due ``d`` becomes a single-op batch
of ``p * 24`` hours due ``start_date + d days`` on one machine/operator. Then APS
"on-time" (``finish < due + 1 day``) reduces exactly to Moore's ``C_j <= d_j``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from core.algorithms.evaluation import compute_metrics
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_proof_harness import (
    TinyBatchSpec,
    TinyBenchmarkCase,
    TinyOperationSpec,
    batch_objects,
    build_folded_fjsp_reference,
    run_case_with_greedy,
)
from tests._support.optimizer_benchmark_loaders import (
    JSP_PROVEN_OPTIMUM,
    SmtwtInstance,
    moore_hodgson_min_tardy,
)

_GRADE_START = datetime(2026, 1, 1, 0, 0, 0)


def smtwt_overdue_case(instance: SmtwtInstance, *, start_dt: datetime = _GRADE_START) -> TinyBenchmarkCase:
    """Build a single-machine APS case from an SMTWT instance (overdue_count scope)."""
    start_date = start_dt.date()
    batches = []
    operations = []
    for idx, (p, d) in enumerate(zip(instance.processing_times, instance.due_dates), start=1):
        batch_id = f"J{idx:03d}"
        due_date = (start_date + timedelta(days=int(d))).isoformat()
        batches.append(TinyBatchSpec(batch_id=batch_id, due_date=due_date, priority="normal"))
        operations.append(
            TinyOperationSpec(
                op_id=idx,
                op_code=f"OP{idx:03d}",
                batch_id=batch_id,
                seq=1,
                machine_id="machine-main",
                operator_id="operator-main",
                duration_hours=float(int(p) * 24),
                op_type_name="standard",
            )
        )
    return TinyBenchmarkCase(
        slug=f"smtwt-{instance.name}",
        objective_name="min_overdue",
        batches=tuple(batches),
        operations=tuple(operations),
        dispatch_mode="sgs",
        dispatch_rule="slack",
        start_dt=start_dt,
    )


def grade_smtwt_overdue(instance: SmtwtInstance) -> Dict[str, Any]:
    """Run greedy on the SMTWT instance and compare overdue_count to the exact optimum.

    Returns greedy vs Moore-optimal tardy counts and the gap. Fails loud if greedy
    leaves any job unscheduled (which would make the comparison meaningless) or if
    greedy beats the proven optimum (which would mean the mapping is wrong).
    """
    case = smtwt_overdue_case(instance)
    results, summary = run_case_with_greedy(case)
    if int(summary.failed_ops) != 0:
        raise ValidationError(
            "SMTWT grading requires every job scheduled on the single machine.",
            field="failed_ops",
            details={"instance": instance.name, "failed_ops": int(summary.failed_ops)},
        )
    metrics = compute_metrics(results, batch_objects(case))
    greedy_overdue = int(metrics.overdue_count)
    optimal_overdue = moore_hodgson_min_tardy(instance.processing_times, instance.due_dates)
    if greedy_overdue < optimal_overdue:
        raise ValidationError(
            "Greedy reported fewer tardy jobs than the proven optimum; the SMTWT "
            "time mapping is inconsistent with the overdue_count metric.",
            field="overdue_count",
            details={
                "instance": instance.name,
                "greedy_overdue": greedy_overdue,
                "optimal_overdue": optimal_overdue,
            },
        )
    return {
        "instance": instance.name,
        "num_jobs": instance.num_jobs,
        "greedy_overdue_count": greedy_overdue,
        "optimal_overdue_count": optimal_overdue,
        "overdue_gap": greedy_overdue - optimal_overdue,
        "is_optimal": greedy_overdue == optimal_overdue,
    }


def build_jsp_folded_reference(name: str, *, actual_makespan_hours: float) -> Dict[str, Any]:
    """Tier-2/3 folded reference: a proven-optimal *makespan* benchmark.

    Job-shop / flexible-job-shop optima are makespan-based, which (per roadmap
    102/274) can only be a ``folded_not_comparable`` reference for the APS
    ``min_overdue`` objective -- never a proof. We feed the proven optimum as the
    reference makespan into the existing folded builder so the gap is tracked but
    explicitly marked not objective comparable. ``build_folded_fjsp_reference``'s
    contract guard rejects any attempt to mark it comparable.
    """
    if name not in JSP_PROVEN_OPTIMUM:
        raise ValidationError("Unknown JSP benchmark instance.", field="name", details={"name": name})
    return build_folded_fjsp_reference(
        case_slug=name,
        objective_name="min_overdue",
        actual_makespan_hours=float(actual_makespan_hours),
        reference_makespan_hours=float(JSP_PROVEN_OPTIMUM[name]),
        # Self-documenting label: the proven optimum is a *makespan*, not a
        # min_overdue proof. Carrying the metric in the label means even a
        # downstream view that shows only the label (and drops reference_type)
        # cannot misread this as an objective-comparable optimum.
        reference_label="proven_optimum_makespan",
    )

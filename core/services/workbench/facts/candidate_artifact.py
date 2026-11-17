"""The stored candidate artifact's one key table: written, compared at adoption and admitted on read.

``run/result_preparation`` builds every artifact from these tables, adoption compares the validated
payload through ``validated_payload_record`` and ``CandidateStore`` admits each stored artifact once with
``admit_artifact`` (D3-5): its exact nested key sets and the values its readers use, so readers index the
keys below directly and use those values as they are. Metrics keep their raw values; the rounded public
projection is ``ScheduleMetrics.numeric_dict`` and is not stored. The business fields are the scheduler's
``BUSINESS_FIELDS``, which the receipt summary's candidates carry too.
"""

from typing import TYPE_CHECKING, Any, Dict, List

from core.algorithms.evaluation_completion import (
    OBJECTIVE_SCOPE_ALL,
    OBJECTIVE_SCOPE_COMPLETED,
    OBJECTIVE_SCOPE_UNKNOWN,
)
from core.models.objective import objective_choice_labels, target_objectives_for
from core.models.workbench_run_job import durable_value
from core.services.scheduler.config.config_field_spec import choices_for
from core.services.scheduler.run.schedule_candidate_plan import BUSINESS_FIELDS, origin_fields
from core.shared.strict_parse import is_exact_positive_int, is_stored_number

from .candidate_values import corrupt, is_stored_text

if TYPE_CHECKING:
    from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
    from core.algorithms.evaluation import ScheduleMetrics
    from core.services.scheduler.run.schedule_payload_contract import ValidatedSchedulePayload

# CandidatePlan attributes stored as they are, besides its business fields.
PLAN_FIELDS = ("sequence", "candidate_key", "label", "used_params", "graph_analysis_public", "graph_analysis_diagnostics",
               "best_order", "algo_mode", "objective_name", "algo_stats", "time_budget_seconds", "dispatch_mode")
# Top level: the plan attributes above, its business fields, then the values the writer derives from the plan and its
# run (``sort_strategy`` is the strategy the plan decoded with, as its choice value).
ARTIFACT_FIELDS = PLAN_FIELDS + BUSINESS_FIELDS + ("sort_strategy", "score", "target_objectives", "summary", "metrics",
                                                   "results", "validated_payload")
# One target direction's evaluation of the plan, as the artifact and the receipt summary store it.
EVALUATION_FIELDS = ("field_order", "score", "scoring_scope")
# A scoring scope as stored and shown: what the score covers, with its operation and batch members counted.
SCORING_SCOPE_FIELDS = ("objective_scope", "components_known", "is_complete", "scheduled_operation_count",
                        "complete_batch_count")
# ScheduleSummary of the candidate's decode.
SUMMARY_FIELDS = ("success", "total_ops", "scheduled_ops", "failed_ops", "warnings", "errors", "duration_seconds",
                  "failure_details")
# ScheduleMetrics, raw; ``completion`` is stored beside them as COMPLETION_FIELDS.
METRICS_FIELDS = ("overdue_count", "total_tardiness_hours", "makespan_hours", "changeover_count",
                  "weighted_tardiness_hours", "makespan_internal_hours", "machine_used_count", "operator_used_count",
                  "machine_busy_hours_total", "operator_busy_hours_total", "machine_util_avg", "operator_util_avg",
                  "machine_load_cv", "operator_load_cv", "internal_horizon_hours", "util_defined", "invalid_due_count",
                  "unscheduled_batch_count", "invalid_due_batch_ids_sample", "unscheduled_batch_ids_sample")
# BatchCompletion, with the objective scope it derives.
COMPLETION_FIELDS = ("expected_operation_count", "missing_operation_count", "unexpected_result_count",
                     "complete_batch_count", "incomplete_batch_ids", "partial_batch_ids", "failure_detail_count",
                     "failure_batch_ids", "explained", "incomplete_work_weight", "objective_scope")
# One ScheduleResult's engine trace; the candidate's task rows own the arrangement itself, and its operation's type
# is the archived operation's (``GenerationFacts.operation_type_labels``).
RESULT_TRACE_FIELDS = ("op_id", "op_code", "batch_id", "seq", "op_type_name", "seed_source", "state_revision")
# ValidatedSchedulePayload's conclusion besides its arrangement rows (D3-7).
VALIDATED_PAYLOAD_FIELDS = ("scheduled_op_ids",)
# The raw metrics the public candidate cards show, admitted as stored numbers (counts are exact integers).
SHOWN_METRICS_FIELDS = ("overdue_count", "total_tardiness_hours", "makespan_hours", "changeover_count",
                        "weighted_tardiness_hours", "machine_used_count", "operator_used_count",
                        "machine_busy_hours_total", "operator_busy_hours_total", "machine_util_avg", "operator_util_avg")
# The summary counts adoption proves a complete decode with (candidate_archive._require_complete_summary).
_SUMMARY_COUNT_FIELDS = ("total_ops", "scheduled_ops", "failed_ops")
# search_evidence_ref: the search event recorded for the candidate's entry (None when there is none) and its run.
_SEARCH_EVIDENCE_KEYS = frozenset(("source_event_id", "run_ref"))

_ARTIFACT_KEYS = frozenset(ARTIFACT_FIELDS)
_SUMMARY_KEYS = frozenset(SUMMARY_FIELDS)
_METRICS_KEYS = frozenset(METRICS_FIELDS + ("completion",))
_COMPLETION_KEYS = frozenset(COMPLETION_FIELDS)
_RESULT_TRACE_KEYS = frozenset(RESULT_TRACE_FIELDS)
_VALIDATED_PAYLOAD_KEYS = frozenset(VALIDATED_PAYLOAD_FIELDS)
_EVALUATION_KEYS = frozenset(EVALUATION_FIELDS)
_SCORING_SCOPE_KEYS = frozenset(SCORING_SCOPE_FIELDS)
_OBJECTIVE_SCOPES = (OBJECTIVE_SCOPE_ALL, OBJECTIVE_SCOPE_COMPLETED, OBJECTIVE_SCOPE_UNKNOWN)
_ALGO_MODES = choices_for("algo_mode")
_SORT_STRATEGIES = choices_for("sort_strategy")
_DISPATCH_MODES = choices_for("dispatch_mode")
# A tuple, as the choices above: a corrupt unhashable value is simply not a member.
_OBJECTIVES = tuple(objective_choice_labels())


def summary_record(summary: "ScheduleSummary") -> Dict[str, Any]:
    return {name: durable_value(getattr(summary, name)) for name in SUMMARY_FIELDS}


def metrics_record(metrics: "ScheduleMetrics") -> Dict[str, Any]:
    record = {name: durable_value(getattr(metrics, name)) for name in METRICS_FIELDS}
    record["completion"] = {name: durable_value(getattr(metrics.completion, name)) for name in COMPLETION_FIELDS}
    return record


def result_traces(results: "List[ScheduleResult]") -> List[Dict[str, Any]]:
    return [{name: durable_value(getattr(row, name)) for name in RESULT_TRACE_FIELDS} for row in results]


def validated_payload_record(payload: "ValidatedSchedulePayload") -> Dict[str, Any]:
    """The validated payload as the artifact stores it; adoption re-validates and compares this same record."""
    return {name: durable_value(getattr(payload, name)) for name in VALIDATED_PAYLOAD_FIELDS}


def scoring_scope_record(scope: Dict[str, Any], *, scheduled: List[Any], complete: List[Any]) -> Dict[str, Any]:
    """The SCORING_SCOPE_FIELDS of a scope whose members are the ``scheduled`` operations and ``complete`` batches
    (their ids in a plan's evaluation and the receipt's selection, their refs in the saved process)."""
    return {"objective_scope": scope["objective_scope"], "components_known": scope["components_known"],
            "is_complete": scope["is_complete"], "scheduled_operation_count": len(scheduled),
            "complete_batch_count": len(complete)}


def evaluation_record(evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """The EVALUATION_FIELDS of one target direction's evaluation, its scope's member ids counted."""
    scope = evaluation["scoring_scope"]
    return {"field_order": evaluation["field_order"], "score": evaluation["score"],
            "scoring_scope": scoring_scope_record(scope, scheduled=scope["scheduled_operation_ids"],
                                                  complete=scope["complete_batch_ids"])}


def _keys_are(value: Any, keys: frozenset) -> bool:
    return type(value) is dict and value.keys() == keys


def _scoring_scope_is_admitted(scope: Any) -> bool:
    """A stored scoring scope as the scope views read it: its objective scope, its two flags and its counts."""
    return (_keys_are(scope, _SCORING_SCOPE_KEYS) and scope["objective_scope"] in _OBJECTIVE_SCOPES
            and type(scope["components_known"]) is bool and type(scope["is_complete"]) is bool
            and is_stored_number(scope["scheduled_operation_count"], integer=True)
            and is_stored_number(scope["complete_batch_count"], integer=True))


def _settings_are_admitted(artifact: Dict[str, Any]) -> bool:
    """The chosen plan's settings as readers show and compare them: its sequence (bound to the candidate row),
    the label, the algorithm mode, strategy and dispatch mode as their choice values, the budget and the strategy
    parameters it ran with."""
    return (is_stored_number(artifact["sequence"], integer=True)
            and is_stored_text(artifact["label"])
            and artifact["algo_mode"] in _ALGO_MODES and artifact["sort_strategy"] in _SORT_STRATEGIES
            and artifact["dispatch_mode"] in _DISPATCH_MODES
            and is_stored_number(artifact["time_budget_seconds"], positive=True)
            and type(artifact["used_params"]) is dict)


def _business_facts_are_admitted(artifact: Dict[str, Any]) -> bool:
    """The primary objective and the target directions the search derives from it, and the business facts tied
    to them: the directions the candidate represents (in target order, possibly none), one evaluation per
    direction with its scoring scope, its origin (keyed as the scheduler writes it for this plan) with the direction
    it searched, when it was first found and the search event it came from."""
    objective = artifact["objective_name"]
    if objective not in _OBJECTIVES:
        return False
    targets = list(target_objectives_for(objective))
    representatives, evidence = artifact["representative_objectives"], artifact["search_evidence_ref"]
    evaluations, origin = artifact["evaluations"], artifact["origin"]
    return (artifact["target_objectives"] == targets
            and type(representatives) is list and representatives == [name for name in targets if name in representatives]
            and type(evaluations) is dict and evaluations.keys() == set(targets)
            and all(_keys_are(evaluation, _EVALUATION_KEYS) and _scoring_scope_is_admitted(evaluation["scoring_scope"])
                    for evaluation in evaluations.values())
            and _keys_are(origin, frozenset(origin_fields(artifact["used_params"])))
            and origin["search_objective"] in targets
            and is_stored_number(artifact["first_found_elapsed_ms"], integer=True)
            and _keys_are(evidence, _SEARCH_EVIDENCE_KEYS)
            and (evidence["source_event_id"] is None or is_exact_positive_int(evidence["source_event_id"])))


def _outcome_is_admitted(artifact: Dict[str, Any]) -> bool:
    """The decode outcome as readers use it: the summary's success, errors and counts, the shown metrics with the
    utilisation flag, the incomplete batches' ids, and the validated operations, each with one engine trace."""
    summary, metrics, results = artifact["summary"], artifact["metrics"], artifact["results"]
    incomplete = metrics["completion"]["incomplete_batch_ids"]
    scheduled = artifact["validated_payload"]["scheduled_op_ids"]
    return (type(summary["success"]) is bool and type(summary["errors"]) is list
            and all(is_stored_number(summary[name], integer=True) for name in _SUMMARY_COUNT_FIELDS)
            and all(is_stored_number(metrics[name], integer=name.endswith("_count")) for name in SHOWN_METRICS_FIELDS)
            and type(metrics["util_defined"]) is bool
            and type(incomplete) is list and all(type(batch_id) is str and batch_id != "" for batch_id in incomplete)
            and type(scheduled) is list and all(is_exact_positive_int(op_id) for op_id in scheduled)
            and len(set(scheduled)) == len(scheduled)
            and all(type(row["op_id"]) is int for row in results)
            and len(results) == len(scheduled) and {row["op_id"] for row in results} == set(scheduled))


def admit_artifact(artifact: Dict[str, Any]) -> Dict[str, Any]:
    """Admit a stored artifact once: its exact nested key sets and the values its readers use; anything else is
    a corrupt archive. The facts it repeats from its candidate row are bound by ``CandidateStore``."""
    if not (_keys_are(artifact, _ARTIFACT_KEYS) and _keys_are(artifact["summary"], _SUMMARY_KEYS)
            and _keys_are(artifact["metrics"], _METRICS_KEYS)
            and _keys_are(artifact["metrics"]["completion"], _COMPLETION_KEYS)
            and _keys_are(artifact["validated_payload"], _VALIDATED_PAYLOAD_KEYS)
            and type(artifact["results"]) is list
            and all(_keys_are(row, _RESULT_TRACE_KEYS) for row in artifact["results"])
            and _settings_are_admitted(artifact) and _business_facts_are_admitted(artifact)
            and _outcome_is_admitted(artifact)):
        corrupt()
    return artifact

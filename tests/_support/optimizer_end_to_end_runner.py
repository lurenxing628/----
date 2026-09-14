"""Measure the real outer comparison and all optimizer phases, using real clocks."""
from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from time import perf_counter
from unittest.mock import patch

from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from core.services.scheduler.run.schedule_candidate_runner import run_candidate_comparison
from core.services.scheduler.run.schedule_optimizer import optimize_schedule
from tests._support.optimizer_end_to_end_cases import (
    OBJECTIVES,
    REPO_ROOT,
    SCENARIOS,
    audit_payload,
    case_environment,
    fixture_data,
    scheduler_config,
    tiny_case,
)
from tests._support.optimizer_end_to_end_io import capture_end_to_end_source
from tests._support.optimizer_end_to_end_schedule import schedule_payload
from tests._support.optimizer_quality_matrix_cases import json_hash
from tests._support.optimizer_quality_matrix_provenance import machine_metadata, proof_binding

DEFAULT_RUN_CONFIG = {"seed": 0, "time_budget_seconds": 1, "run_time_budget_seconds": 5.0,
                      "weight_count": 3, "workers": 1, "selection_policy": "score_only", "decoder_count_mode": "native"}
MEASUREMENT = {"clock": "time.perf_counter", "execution": "serial_single_worker",
               "scope": "candidate_comparison_including_graph_preparation_and_full_optimizer_excludes_fixture_and_audit",
               "decoder_count_source": "native_scheduler_counter"}


def measurement_for_config(config):
    return dict(MEASUREMENT, decoder_count_source=("native_scheduler_counter" if config["decoder_count_mode"] == "native"
                                                 else "unmeasured"))


def validate_config(config):
    if not isinstance(config, dict) or set(config) != set(DEFAULT_RUN_CONFIG):
        raise ValueError("unknown or missing end-to-end run config")
    for key in ("seed", "time_budget_seconds", "weight_count", "workers"):
        if type(config[key]) is not int:
            raise ValueError("integer config required: " + key)
    if config["seed"] < 0 or not 1 <= config["time_budget_seconds"] <= 300:
        raise ValueError("invalid seed or optimizer budget")
    budget = config["run_time_budget_seconds"]
    if type(budget) not in (int, float) or not math.isfinite(budget) or not 0 < budget <= 3600:
        raise ValueError("invalid comparison budget")
    if config["workers"] != 1 or config["weight_count"] not in (3, 5, 7):
        raise ValueError("single-worker measurement and supported candidate weight count required")
    if config["selection_policy"] != "score_only":
        raise ValueError("this benchmark measures score_only selection")
    if config["decoder_count_mode"] not in ("native", "uncounted"):
        raise ValueError("decoder_count_mode must be native or uncounted")


class _Measurement:
    def __init__(self, objective, decoder_count_mode):
        self.objective = objective
        self.decoder_count_mode = decoder_count_mode
        self.started = perf_counter()
        self.initial_score = None
        self.first_improvement_ms = None
        self.optimizer_calls = []
        self.accept = OptimizationSearchReportState.mark_candidate_accepted

    @property
    def decode_count(self):
        if self.decoder_count_mode == "uncounted":
            return None
        return sum(call["decode_count"] for call in self.optimizer_calls)

    def accepted(self, state, candidate, **kwargs):
        outcome = self.accept(state, candidate, **kwargs)
        # Observe an already-computed production score; no extra metrics work inside the timer.
        score = tuple(candidate["score"])
        if self.initial_score is None:
            self.initial_score = score
        elif self.first_improvement_ms is None and score < self.initial_score:
            self.first_improvement_ms = (perf_counter() - self.started) * 1000
        return outcome

    def optimize(self, **kwargs):
        started = perf_counter()
        outcome = optimize_schedule(**kwargs)
        count = None
        if self.decoder_count_mode == "native":
            report = outcome.search_report
            count = report.get("decoder_invocations") if isinstance(report, dict) else None
            if type(count) is not int or count < 1:
                raise ValueError("native decoder counter unavailable or invalid; legacy sources require explicit uncounted mode")
        self.optimizer_calls.append({"decode_count": count,
                                     "optimizer_runtime_ms": (perf_counter() - started) * 1000})
        return outcome


def run_case(scenario, objective, config=None):
    config = dict(DEFAULT_RUN_CONFIG if config is None else config)
    validate_config(config)
    if os.environ.get("PYTEST_XDIST_WORKER"):
        raise ValueError("run end-to-end matrix without xdist")
    data = fixture_data(scenario)
    with case_environment(data, objective, config) as schedule_input:
        measurement = _Measurement(objective, config["decoder_count_mode"])

        def observed_accept(state, candidate, **kwargs):
            return measurement.accepted(state, candidate, **kwargs)

        with patch.object(OptimizationSearchReportState, "mark_candidate_accepted", new=observed_accept):
            outcome = run_candidate_comparison(
                schedule_input=schedule_input, optimize_schedule_fn=measurement.optimize, clock=perf_counter,
                run_time_budget_seconds=config["run_time_budget_seconds"], weight_count=config["weight_count"],
                selection_policy=config["selection_policy"], strict_mode=True,
            )
        runtime_ms = (perf_counter() - measurement.started) * 1000
        selected = outcome.selection.selected_plan
        baseline = next(plan for plan in outcome.candidates if plan.candidate_key == "baseline")
        before, after = schedule_payload(baseline, schedule_input), schedule_payload(selected, schedule_input)
        errors = []
        for label, payload in (("baseline", before), ("selected", after)):
            try:
                audit_payload(payload, data)
            except ValueError as exc:
                errors.append(label + ": " + str(exc))
        if tuple(after["quality_vectors"][objective]) > tuple(before["quality_vectors"][objective]):
            errors.append("selected objective regressed against outer baseline")
        return {"case_id": scenario + "/" + objective, "scenario": scenario, "objective": objective,
                "fixture_sha256": json_hash(data), "scheduler_config": scheduler_config(scenario, objective, config),
                "operation_count": len(data["operations"]), "constraint_tags": data["constraint_tags"],
                "runtime_ms": runtime_ms, "decode_count": measurement.decode_count,
                "optimizer_call_count": len(measurement.optimizer_calls),
                "first_improvement_ms": measurement.first_improvement_ms,
                "selected_candidate_key": selected.candidate_key,
                "candidates": _candidate_rows(outcome.candidates, measurement.optimizer_calls, schedule_input, config),
                "baseline": before, "selected": after, "oracle": oracle_report(data, after),
                "status": "failed" if errors else "passed", "errors": errors}


def _candidate_rows(candidates, calls, schedule_input, config):
    records, call_index = [], 0
    for plan in candidates:
        completed = plan.status == "completed"
        reused_from = plan.reused_from_candidate_key
        executed = completed and reused_from is None
        empty_count = 0 if config["decoder_count_mode"] == "native" else None
        call = calls[call_index] if executed else {"decode_count": empty_count, "optimizer_runtime_ms": 0.0}
        call_index += int(executed)
        records.append({"candidate_key": plan.candidate_key, "status": plan.status, "reused_from": reused_from,
                        "score": list(plan.score) if completed else None, "runtime_ms": plan.elapsed_seconds * 1000,
                        "quality_vectors": schedule_payload(plan, schedule_input)["quality_vectors"] if completed else None,
                        **call})
    if call_index != len(calls):
        raise ValueError("optimizer call accounting mismatch")
    return records


def oracle_report(data, payload):
    if not data["scenario"].startswith("tiny_"):
        return {"applicable": False, "reason": "outside_restricted_tiny_domain", "optimum_vectors": None,
                "selected_vectors": None, "lexicographic_gaps": None}
    from tests._support.optimizer_exact_oracle import ScheduledOperation, score_schedule, solve_exact

    case = tiny_case(data["scenario"])
    start = datetime.fromisoformat(data["start_dt"])
    schedule = []
    for row in payload["schedule"]:
        minutes = [(datetime.fromisoformat(row[key]) - start).total_seconds() / 60 for key in ("start_time", "end_time")]
        if any(value != int(value) for value in minutes):
            raise ValueError("tiny oracle requires exact integer-minute schedule")
        schedule.append(ScheduledOperation(row["op_id"], int(minutes[0]), int(minutes[1]), row["machine_id"], row["operator_id"]))
    best, selected, gaps = {}, {}, {}
    for objective in OBJECTIVES:
        best[objective] = list(solve_exact(case, objective).best_score)
        selected[objective] = list(score_schedule(case, tuple(schedule), objective))
        if selected[objective] != payload["quality_vectors"][objective]:
            raise ValueError("independent oracle disagrees with production quality vector")
        if tuple(selected[objective]) < tuple(best[objective]):
            raise ValueError("schedule claims score better than independent optimum")
        index = next((i for i, pair in enumerate(zip(selected[objective], best[objective])) if pair[0] != pair[1]), None)
        gaps[objective] = {"first_differing_index": index,
                           "delta": selected[objective][index] - best[objective][index] if index is not None else 0.0,
                           "optimal": index is None}
    return {"applicable": True, "reason": "exact_single_resource_zero_release_24h_no_setup",
            "optimum_vectors": best, "selected_vectors": selected, "lexicographic_gaps": gaps}


def build_end_to_end_matrix(config=None, scenarios=None, objectives=None):
    config = dict(DEFAULT_RUN_CONFIG if config is None else config)
    validate_config(config)
    scenarios = list(SCENARIOS if scenarios is None else scenarios)
    objectives = list(OBJECTIVES if objectives is None else objectives)
    for values, allowed in ((scenarios, SCENARIOS), (objectives, OBJECTIVES)):
        if not values or len(values) != len(set(values)) or any(value not in allowed for value in values):
            raise ValueError("unknown, empty or duplicate matrix coverage")
    before, started = capture_end_to_end_source(REPO_ROOT), datetime.now(timezone.utc).isoformat()
    cases = [run_case(scenario, objective, config) for scenario in scenarios for objective in objectives]
    after = capture_end_to_end_source(REPO_ROOT)
    return {"schema_version": 1, "kind": "optimizer_end_to_end_matrix",
            "claim": "feasibility_and_restricted_tiny_oracle_not_general_optimality", "config": config,
            "coverage": {"scenarios": scenarios, "objectives": objectives}, "measurement": measurement_for_config(config),
            "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(), "machine": machine_metadata(),
            "source_before": before, "source_after": after, "proof_binding": proof_binding(before, after),
            "cases": cases, "status": "passed" if all(row["status"] == "passed" for row in cases) else "failed"}

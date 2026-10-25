"""Saved candidate solver facts, with explicit legacy and reuse coverage."""

import math

from core.models.objective import best_score_schema, comparison_metric_key, objective_choice_labels
from core.services.scheduler.contracts.optimizer_public_safety import (
    PUBLIC_ATTEMPT_METRIC_KEYS,
    project_attempt_metrics,
    safe_counter_dict,
)
from core.services.scheduler.contracts.optimizer_public_search_report import project_search_report
from core.services.scheduler.summary.optimizer_public_attempts import project_attempt_evaluation, project_attempts

from .candidate_values import corrupt

PROCESS_VERSION = "decision-process-v1"
EVIDENCE_VERSION = "optimization-process-v1"
COUNT_KEYS = ("evaluated", "accepted", "current_accepted", "strict_improvements", "rejected", "unverified_trials", "decoder_invocations")
COMPLETION_KEYS = ("expected_operation_count", "missing_operation_count", "unexpected_result_count", "complete_batch_count", "incomplete_batch_count")
_REPORT_COUNTS = {"evaluated": "evaluated_candidates", "accepted": "accepted_candidates", "current_accepted": "current_accepted_candidates",
                  "rejected": "rejected_candidates", "decoder_invocations": "decoder_invocations"}
_STOP_LABELS = {"time_budget": "计算时间预算已用完", "iteration_limit": "达到迭代上限", "search_exhausted": "搜索范围已完成",
                "baseline_scheduled": "原算法安排已生成", "all_candidates_rejected": "尝试均未通过接受检查", "no_improvement": "本次搜索未得到改善",
                "completed": "本候选计算已完成", "candidate_time_budget_reached": "本轮计算时间预算已用完"}


def _number(value, *, integer=False):
    if type(value) not in ((int,) if integer else (int, float)):
        return None
    return value if value >= 0 and math.isfinite(value) else None


def _dict(value):
    if value is None:
        return {}
    if type(value) is not dict:
        corrupt()
    return value


def _rows(value):
    if value is None:
        return []
    if type(value) is not list or any(type(row) is not dict for row in value):
        corrupt()
    return value


def _text(value):
    return value if type(value) is str and value.strip() else None


def _score(value):
    if value is None:
        return []
    if type(value) not in (list, tuple):
        corrupt()
    return [_number(item) for item in value]


def _objective_values(score, primary, completion):
    return project_attempt_evaluation(_score(score), _number(primary), completion)


def _counts(evidence, report):
    if evidence:
        raw = _dict(evidence.get("counts"))
        return {key: _number(raw.get(key), integer=True) for key in COUNT_KEYS}
    return {key: _number(report.get(_REPORT_COUNTS.get(key)), integer=True) for key in COUNT_KEYS}


def _completion(raw):
    result = {key: _number(raw.get(key), integer=True) for key in COMPLETION_KEYS}
    # Older metric artifacts save this exact membership rather than its count.
    if result["incomplete_batch_count"] is None and type(raw.get("incomplete_batch_ids")) is list:
        result["incomplete_batch_count"] = len(raw["incomplete_batch_ids"])
    return result


def candidate_objective(artifact, evidence, report):
    saved = _dict(evidence.get("objective"))
    name = _text(saved.get("name")) or _text(artifact.get("objective_name")) or _text(report.get("objective_name")) or _text(artifact.get("objective"))
    labels = objective_choice_labels()
    known = name in labels
    primary = _text(saved.get("primary_metric_key")) or (comparison_metric_key(name) if known else None)
    fields = _rows(saved.get("score_fields")) or (best_score_schema(name) if known else [])
    fields = [{"index": _number(row.get("index"), integer=True), "key": _text(row.get("key")), "label": _text(row.get("label")),
               "unit": _text(row.get("unit")) or _unit(row.get("key")), "direction": "lower"} for row in fields]
    for field in fields:
        if field["key"] == "changeover_count":
            field["label"] = "算法工种切换次数"
    field = next((row for row in fields if row["key"] == primary), {})
    return {"name": name, "label": "最少算法工种切换次数" if name == "min_changeover" else (labels.get(name) if name is not None else None),
            "primary_metric_key": primary, "primary_metric_label": field.get("label"),
            "unit": _text(saved.get("unit")) or field.get("unit"), "score_fields": fields}


def _unit(key):
    return "工序" if key == "failed_ops" else "批次" if key == "overdue_count" else "次" if key == "changeover_count" else "小时" if str(key).endswith("_hours") else None


def _stop(code):
    code = _text(code)
    return {"code": code, "message": _STOP_LABELS.get(code, code)} if code else None


def _solver_row(row, rows):
    artifact = row["artifact"]
    evidence = _dict(artifact.get("process_evidence"))
    source = _dict(evidence.get("source"))
    ref, key = source.get("reused_from_candidate_ref"), artifact.get("reused_from_candidate_key") or source.get("reused_from_candidate_key")
    reused = source.get("kind") == "reused" or ref is not None or key is not None
    if not reused:
        return row, False
    current, seen = row, set()
    while ref is not None or key is not None:
        if current["candidate_ref"] in seen:
            corrupt()
        seen.add(current["candidate_ref"])
        current = next((item for item in rows if item["candidate_ref"] == ref), None) if ref is not None else next(
            (item for item in rows if item["artifact"].get("candidate_key") == key), None)
        if current is None:
            return None, True
        nested = _dict(_dict(current["artifact"].get("process_evidence")).get("source"))
        ref = nested.get("reused_from_candidate_ref")
        key = current["artifact"].get("reused_from_candidate_key") or nested.get("reused_from_candidate_key")
    return current, True


def _sampling(evidence, points):
    saved = _dict(evidence.get("sampling"))
    return {"policy": _text(saved.get("policy")) if evidence else "legacy_saved_events", "point_budget": 200,
            "event_total_count": _number(saved.get("event_total_count"), integer=True), "retained_point_count": len(points),
            "bucket_count": _number(saved.get("bucket_count"), integer=True), "bucket_width_ms": _number(saved.get("bucket_width_ms")),
            "mandatory": list(saved.get("mandatory") or []) if evidence else []}


def _points(artifact, evidence, objective, source_ref):
    raw = _rows(evidence.get("points") if evidence else artifact.get("improvement_trace"))
    if len(raw) > 200:
        corrupt()
    result = []
    for index, row in enumerate(raw):
        flags = row.get("flags") or []
        if evidence and (type(flags) is not list or any(flag not in ("first_valid", "first_expected_complete", "final", "strict_improvement", "segment_start") for flag in flags)):
            corrupt()
        metrics = _dict(row.get("metrics"))
        raw_completion = _dict(row.get("completion") if evidence else metrics.get("completion"))
        objective_context = {"objective_scope": row.get("objective_scope")} if evidence else raw_completion
        score, primary = _objective_values(row.get("score"), row.get("primary_value") if evidence else metrics.get(objective["primary_metric_key"]), objective_context)
        completion = _completion(raw_completion)
        evaluation_scope = row.get("evaluation_scope") if evidence else None
        if (evaluation_scope is None and objective_context.get("objective_scope") == "all_batches"
                and completion["incomplete_batch_count"] == 0 and row.get("verified") is not False):
            evaluation_scope = {"incomplete_batch_ids": []}
        if evaluation_scope is not None:
            members = _dict(evaluation_scope).get("incomplete_batch_ids")
            if type(members) is not list or any(_text(member) is None for member in members):
                corrupt()
            evaluation_scope = {"incomplete_batch_ids": list(members)}
        result.append({"source_candidate_ref": source_ref, "event_index": _number(row.get("event_index"), integer=True) if evidence else index + 1,
            "elapsed_ms": _number(row.get("elapsed_ms")), "phase": _text(row.get("phase")), "phase_visit": _number(row.get("phase_visit"), integer=True),
            "segment": _number(row.get("segment"), integer=True), "flags": list(flags) if evidence else [],
            "score": score, "primary_value": primary,
            "objective_scope": _text(objective_context.get("objective_scope")),
            "completion": completion, "evaluation_scope": evaluation_scope,
            "verified": row.get("verified") if type(row.get("verified")) is bool and evidence else None})
    return result


def _attempts(artifact, objective, source_ref):
    result = []
    for index, raw in enumerate(_rows(artifact.get("attempts"))):
        if raw.get("candidate_status") == "phase_summary":
            continue
        public, _ = project_attempts([raw])
        if not public:
            continue
        item = public[0]
        metrics = item.get("metrics") or {}
        completion = metrics.get("completion") or {}
        raw_completion = _dict(_dict(raw.get("metrics")).get("completion"))
        public_completion = _completion(raw_completion)
        score, primary = _objective_values(raw.get("score"), metrics.get(objective["primary_metric_key"]), raw_completion)
        result.append({"source_candidate_ref": source_ref, "saved_index": index + 1, "rank": None,
            **{key: item.get(key) for key in ("strategy", "dispatch_mode", "dispatch_rule", "candidate_status", "source_label", "failed_ops")},
            **{key: item.get(key) for key in ("candidate_origin", "weight_profile_slug", "event_index", "verified", "strict_improved", "comparison")},
            "score": score, "metrics": {key: _number(metrics.get(key)) for key in sorted(PUBLIC_ATTEMPT_METRIC_KEYS)},
            "primary_value": primary, "objective_scope": _text(completion.get("objective_scope")),
            "completion": public_completion, "elapsed_ms": _number(raw.get("elapsed_ms")),
            "accepted": item.get("accepted")})
    valid = [row for row in result if row["score"] and all(value is not None for value in row["score"])]
    valid.sort(key=lambda row: (tuple(row["score"]), row["saved_index"]))
    for rank, row in enumerate(valid, 1):
        row["rank"] = rank
    return result


def _stages(evidence, report):
    if not evidence:
        return [{"phase": _text(row.get("phase")), "start_elapsed_ms": None, "end_elapsed_ms": None, "elapsed_ms": None,
                 "visits": None, "evaluated": None, "accepted": None, "strict_improvements": None, "rejected": None,
                 "stop_reason": _text(row.get("reason")), "status": "skipped"} for row in _rows(report.get("skipped_phases"))]
    return [{**{key: _number(row.get(key), integer=key in ("visits", "evaluated", "accepted", "strict_improvements", "rejected"))
                for key in ("start_elapsed_ms", "end_elapsed_ms", "elapsed_ms", "visits", "evaluated", "accepted", "strict_improvements", "rejected")},
             **{key: _text(row.get(key)) for key in ("phase", "status", "stop_reason")}} for row in _rows(evidence.get("stages"))]


def candidate_process(row, rows):
    """Project one member and its actual solver source without changing viewer identity."""
    own = row["artifact"]
    solver, reused = _solver_row(row, rows)
    artifact = solver["artifact"] if solver is not None else {}
    evidence, report = _dict(artifact.get("process_evidence")), _dict(artifact.get("search_report"))
    own_evidence = _dict(own.get("process_evidence"))
    if evidence and evidence.get("version") != EVIDENCE_VERSION:
        corrupt()
    if evidence and evidence.get("state") not in ("complete", "unavailable"):
        corrupt()
    source_ref = solver["candidate_ref"] if solver else None
    objective = candidate_objective(artifact, evidence, report)
    points, attempts = _points(artifact, evidence, objective, source_ref), _attempts(artifact, objective, source_ref)
    available = solver is not None and (evidence.get("state") == "complete" if evidence else bool(report or points or attempts))
    state = "complete" if available and evidence else "partial" if available else "unavailable"
    reason = None if state == "complete" else {"code": "legacy_process_coverage" if available else "process_not_recorded",
        "message": "旧记录展示已保存的代表尝试和离散事件；本次计算的首尾标记与阶段计数未完整保存。" if available else "该候选没有保存可查看的求解过程。"}
    kind = "reused" if reused else _dict(own_evidence.get("source")).get("kind") or ("failed" if row["status"] == "failed" else "not_started" if row["status"] == "skipped" else "own_search")
    if kind not in ("own_search", "reused", "failed", "not_started", "budget_skipped"):
        corrupt()
    solver_counts = _counts(evidence, report)
    legacy_updates = None if evidence else _number(report.get("best_improved_candidates"), integer=True)
    profile, _ = project_search_report(report)
    rejected = evidence.get("rejection_summary") if evidence else report.get("rejection_summary")
    rejection_summary = safe_counter_dict(_dict(rejected)) if rejected is not None else None
    own_counts = {key: 0 for key in COUNT_KEYS} if reused else _counts(own_evidence, _dict(own.get("search_report")))
    elapsed = _number(own.get("elapsed_seconds"))
    own_elapsed = elapsed * 1000 if elapsed is not None else None
    solver_elapsed = _number(evidence.get("elapsed_ms")) if evidence else _number(report.get("runtime_ms"))
    stop = _stop(evidence.get("stop_reason") if evidence else report.get("stop_reason")) or _stop(own.get("failure_reason"))
    final_raw = _dict(own.get("metrics"))
    final_safe = project_attempt_metrics(final_raw)
    final_metrics = {key: _number(final_safe.get(key)) for key in sorted(PUBLIC_ATTEMPT_METRIC_KEYS)}
    completion = _completion(_dict(final_raw.get("completion")))
    sampling = _sampling(evidence, points)
    endpoints = {flag: any(flag in point["flags"] for point in points) if evidence and available else None
                 for flag in ("first_valid", "first_expected_complete", "final")}
    coverage = {"state": state, "reason": reason, "endpoint_coverage": endpoints}
    metadata = {"candidate_ref": row["candidate_ref"], "label": _text(own.get("label")), "status": row["status"], "persisted_status": row["status"],
        "kind": _text(own.get("kind")), **{key: _text(own.get(key)) for key in ("algo_mode", "used_strategy", "dispatch_mode")},
        "configured_dispatch_rule": _text(own.get("dispatch_rule")), "adopted_dispatch_rule": _text(own.get("adopted_dispatch_rule")),
        "source_kind": kind, "source_candidate_ref": source_ref, "own_elapsed_ms": own_elapsed, "source_solver_elapsed_ms": solver_elapsed,
        "own_counts": own_counts, "solver_counts": solver_counts, "stop_reason": stop, "final_metrics": final_metrics, "completion": completion,
        "algorithm_profile": _text(report.get("algorithm_profile")), "legacy_best_updates": legacy_updates,
        "evidence_state": state, "evidence_version": evidence.get("version") if evidence else None}
    return {"candidate": metadata, "source": {"role": "process_anchor", "grain": "saved_candidate_solver_process", "kind": kind,
        "candidate_ref": row["candidate_ref"], "source_candidate_ref": source_ref, "available": available, "evidence_state": state,
        "evidence_version": metadata["evidence_version"], "reason": reason, "profile": profile.get("profile_public", {}), "rejection_summary": rejection_summary},
        "summary": {"own_elapsed_ms": own_elapsed, "source_solver_elapsed_ms": solver_elapsed, "own_counts": own_counts,
            "solver_counts": solver_counts, "saved_attempt_count": len(attempts), "retained_point_count": len(points), "stop_reason": stop,
            "coverage": {"state": state, "reason": reason}, "sampling": sampling, "legacy_best_updates": legacy_updates,
            "rejection_summary": rejection_summary}, "objective": objective,
        "progress": {"mode": "curve" if evidence and available and points else "discrete" if points else "none", "points": points,
            "source_candidate_ref": source_ref, "sampling": sampling, "coverage": coverage},
        "stages": _stages(evidence, report), "attempts": attempts}

"""Small runtime facts for optimization progress, sampled only after the actual elapsed time is known.

Runtime storage is O(effective progress events), with scores and evaluation
coverage facts only. The completed artifact has at most 200 points; no decoded arrangements
or complete candidate objects are retained by this collector.
"""
from __future__ import annotations

import math
from contextlib import contextmanager
from copy import deepcopy
from typing import Any, Dict, List, Optional

from core.models.objective import best_score_schema, comparison_metric_key

PROCESS_EVIDENCE_VERSION = "optimization-process-v1"
POINT_BUDGET = 200
SAMPLING_POLICY = "elapsed_equal_width_bucket_end_best_v1"
_MANDATORY = ("first_valid", "first_expected_complete", "final")
_COUNT_KEYS = ("evaluated", "accepted", "current_accepted", "strict_improvements", "rejected", "unverified_trials",
               "decoder_invocations")
_UNITS = {"failed_ops": "工序", "overdue_count": "批次", "changeover_count": "次"}


def process_objective(objective_name: str) -> Dict[str, Any]:
    fields = [{**row, "unit": _UNITS.get(row["key"], "小时"), "direction": "lower"}
              for row in best_score_schema(objective_name)]
    key = comparison_metric_key(objective_name)
    return {"name": objective_name, "score_fields": fields, "primary_metric_key": key,
            "unit": _UNITS.get(key, "小时")}


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def sample_elapsed_points(points: List[Dict[str, Any]], *, elapsed_ms: int, limit: int = POINT_BUDGET):
    """Keep milestones and the last incumbent event in each equal elapsed-time bucket."""
    mandatory = {index for index, row in enumerate(points) if set(row.get("flags", ())) & set(_MANDATORY)}
    slots = max(int(limit) - len(mandatory), 0)
    buckets: Dict[int, int] = {}
    if slots:
        for index, row in enumerate(points):
            bucket = min(int(row["elapsed_ms"] * slots / elapsed_ms), slots - 1) if elapsed_ms else 0
            buckets[bucket] = index
    selected = sorted(mandatory | set(buckets.values()))
    return [deepcopy(points[index]) for index in selected], {
        "policy": SAMPLING_POLICY, "point_budget": int(limit), "event_total_count": len(points),
        "retained_point_count": len(selected), "bucket_count": slots,
        "bucket_width_ms": elapsed_ms / slots if slots else None, "mandatory": list(_MANDATORY),
    }


def sample_legacy_trace(rows: List[Dict[str, Any]], *, elapsed_ms: Optional[int] = None, limit: int = POINT_BUDGET):
    """Apply the same final sampling to existing trace rows without changing their shape."""
    if not rows:
        return []
    points = []
    first_complete = False
    for index, row in enumerate(rows):
        completion = (row.get("metrics") or {}).get("completion") or {}
        score = row.get("score") or []
        complete = (completion.get("missing_operation_count") == 0
                    and completion.get("unexpected_result_count") == 0 and bool(score) and score[0] == 0)
        flags = (["first_valid"] if index == 0 else []) + (["final"] if index == len(rows) - 1 else [])
        if complete and not first_complete:
            flags.append("first_expected_complete")
            first_complete = True
        points.append({"elapsed_ms": max(int(row.get("elapsed_ms") or 0), 0), "flags": flags, "row": row})
    duration = max(int(elapsed_ms or 0), max(point["elapsed_ms"] for point in points))
    sampled, _policy = sample_elapsed_points(points, elapsed_ms=duration, limit=limit)
    return [point["row"] for point in sampled]


def non_search_evidence(objective_name: str, *, kind: str, reason: Optional[str], elapsed_ms=None,
                        known_not_started: bool = False, source_candidate_key: Optional[str] = None):
    """Known zero work and unavailable runtime history have different counter values."""
    known_zero = known_not_started or kind == "reused"
    return {
        "version": PROCESS_EVIDENCE_VERSION, "state": "complete" if known_zero else "unavailable",
        "source": {"kind": kind, "reused_from_candidate_key": source_candidate_key},
        "objective": process_objective(objective_name), "elapsed_ms": 0 if known_zero else elapsed_ms,
        "stop_reason": reason, "counts": {key: 0 if known_zero else None for key in _COUNT_KEYS},
        "rejection_summary": {} if known_zero else None,
        "sampling": {"policy": "not_applicable", "point_budget": POINT_BUDGET, "event_total_count": 0 if known_zero else None,
                     "retained_point_count": 0, "bucket_count": 0, "bucket_width_ms": None, "mandatory": list(_MANDATORY)},
        "points": [], "stages": [],
    }


class OptimizationProcessEvidence:
    def __init__(self, *, objective_name: str, clock, started_at: float):
        self.objective = process_objective(objective_name)
        self.clock, self.started_at = clock, float(started_at)
        self.counts: Dict[str, Any] = {key: 0 for key in _COUNT_KEYS}
        self.counts["decoder_invocations"] = None
        self._points: List[Dict[str, Any]] = []
        self._point_by_event: Dict[int, Dict[str, Any]] = {}
        self._event_index = 0
        self._last_elapsed = 0
        self._pending_id: Optional[int] = None
        self._pending: Any = None
        self._best_score: Any = None
        self._best_context: Any = None
        self._coverage_context: Any = None
        self._best_plot_context: Any = None
        self._has_valid = False
        self._has_complete = False
        self._stages: Dict[str, Dict[str, Any]] = {}
        self.rejection_summary: Dict[str, int] = {}
        self._phase = None
        self._visit = 0
        self._visit_index = 0
        self._segment = 0
        self._active_since = self.started_at
        self._stack = []
        self._final = None

    def _elapsed(self, at=None):
        now = self.clock() if at is None else at
        self._last_elapsed = max(self._last_elapsed, int((now - self.started_at) * 1000), 0)
        return self._last_elapsed

    def _stage(self, name):
        return self._stages.setdefault(name, {
            "phase": name, "start_elapsed_ms": None, "end_elapsed_ms": None, "elapsed_ms": 0.0,
            "visits": 0, "evaluated": 0, "accepted": 0, "strict_improvements": 0, "rejected": 0,
            "stop_reason": None, "status": "completed",
        })

    def _charge_phase(self, at):
        if self._phase is not None:
            stage = self._stage(self._phase)
            stage["elapsed_ms"] += max((at - self._active_since) * 1000, 0.0)
            stage["end_elapsed_ms"] = self._elapsed(at)
        self._active_since = at

    def begin_phase(self, name: str, *, at=None):
        now = self.clock() if at is None else at
        self._charge_phase(now)
        self._stack.append((self._phase, self._visit))
        self._phase = name
        self._visit_index += 1
        self._visit = self._visit_index
        self._segment += 1
        stage = self._stage(name)
        elapsed = self._elapsed(now)
        if stage["start_elapsed_ms"] is None:
            stage["start_elapsed_ms"] = elapsed
        stage["end_elapsed_ms"] = elapsed
        stage["visits"] += 1

    def end_phase(self, *, at=None, failed: Optional[str] = None):
        now = self.clock() if at is None else at
        self._charge_phase(now)
        if failed is not None and self._phase is not None:
            self._stage(self._phase).update(status="failed", stop_reason=failed)
        self._phase, self._visit = self._stack.pop()
        self._segment += 1

    @contextmanager
    def phase(self, name: str):
        self.begin_phase(name)
        try:
            yield
        except Exception as exc:
            self.end_phase(failed=type(exc).__name__)
            raise
        else:
            self.end_phase()

    def call(self, name, fn, *args, **kwargs):
        with self.phase(name):
            return fn(*args, **kwargs)

    def skipped_phase(self, name: str, reason: str):
        stage = self._stage(name)
        stage["stop_reason"] = reason
        if not stage["evaluated"]:
            stage["status"] = "skipped"

    def phase_stop(self, name: str, reason: Optional[str]):
        stage = self._stage(name)
        if reason is not None:
            stage["stop_reason"] = reason
        if not stage["visits"] and stage["status"] != "failed":
            stage["status"] = "skipped"

    def _count(self, key, *, origin=None):
        self.counts[key] += 1
        phase = self._phase or origin
        if phase is not None and key in self._stage(phase):
            self._stage(phase)[key] += 1

    def _snapshot(self, candidate, *, origin, verified, event_index, elapsed_ms):
        metrics = candidate.get("metrics")
        completion = getattr(metrics, "completion", None)
        scope = getattr(completion, "objective_scope", "unknown")
        known = bool(completion is not None and completion.components_known)
        values = [_number(value) for value in candidate.get("score", ())]
        if not known:
            values = [values[0] if values else None] + [None for _ in values[1:]]
        counts = {key: getattr(completion, key, None) for key in (
            "expected_operation_count", "missing_operation_count", "unexpected_result_count", "complete_batch_count")}
        counts["incomplete_batch_count"] = len(completion.incomplete_batch_ids) if completion is not None else None
        summary = candidate.get("summary")
        complete = bool(verified and completion is not None and counts["missing_operation_count"] == 0
                        and counts["unexpected_result_count"] == 0 and getattr(summary, "failed_ops", None) == 0
                        and getattr(summary, "success", None) is True)
        key = self.objective["primary_metric_key"]
        primary = _number(getattr(metrics, key, None)) if known else None
        phase = self._phase or origin
        context = (scope, tuple(completion.incomplete_batch_ids) if completion is not None else None,
                   counts["expected_operation_count"])
        if verified and context != self._coverage_context:
            if self._coverage_context is not None:
                self._segment += 1
            self._coverage_context = context
        point = {"event_index": event_index, "elapsed_ms": elapsed_ms, "phase": phase, "phase_visit": self._visit,
                 "segment": self._segment, "flags": [], "score": values, "primary_value": primary,
                 "objective_scope": scope, "completion": counts, "verified": bool(verified),
                 "evaluation_scope": {"incomplete_batch_ids": list(completion.incomplete_batch_ids)} if verified and completion is not None and known else None}
        valid = bool(verified and primary is not None and len(values) == len(self.objective["score_fields"])
                     and all(value is not None for value in values))
        return point, context, valid, complete

    def _remember(self, point, flags):
        index = point["event_index"]
        if index in self._point_by_event:
            target = self._point_by_event[index]
        else:
            target = point
            self._point_by_event[index] = target
            self._points.append(target)
        for flag in flags:
            if flag not in target["flags"]:
                target["flags"].append(flag)

    def evaluated(self, candidate, *, origin, verified=True):
        self._count("evaluated", origin=origin)
        if not verified:
            self._count("unverified_trials", origin=origin)
        self._event_index += 1
        self._pending_id = id(candidate)
        self._pending = self._snapshot(candidate, origin=origin, verified=verified,
                                       event_index=self._event_index, elapsed_ms=self._elapsed())
        point, _context, valid, complete = self._pending
        flags = []
        if valid and not self._has_valid:
            self._has_valid = True
            flags.append("first_valid")
        if complete and not self._has_complete:
            self._has_complete = True
            flags.append("first_expected_complete")
        if flags:
            self._remember(point, flags)

    def last_evaluation_fact(self, candidate):
        """The actual evaluation stamp for the currently recorded candidate, without another clock read."""
        if self._pending_id != id(candidate) or self._pending is None:
            return None
        point = self._pending[0]
        return {key: point[key] for key in ("event_index", "elapsed_ms", "verified")}

    def accepted(self, candidate, *, origin, current_only=False):
        self._count("accepted", origin=origin)
        if current_only:
            self._count("current_accepted", origin=origin)
            return
        if self._pending_id != id(candidate):
            self._event_index += 1
            snapshot = self._snapshot(candidate, origin=origin, verified=True,
                                      event_index=self._event_index, elapsed_ms=self._elapsed())
        else:
            snapshot = self._pending
        point, context, valid, _complete = snapshot
        score = tuple(point["score"])
        same_context = context == self._best_context
        plot_context = point["phase"], point["phase_visit"], point["segment"]
        improved = bool(valid and same_context and self._best_score is not None and score < self._best_score)
        if improved:
            self._count("strict_improvements", origin=origin)
        if self._best_score is None or not same_context or plot_context != self._best_plot_context or improved:
            flags = ["strict_improvement"] if improved else ["segment_start"]
            self._remember(point, flags)
        if valid:
            self._best_score, self._best_context = score, context
        self._best_plot_context = plot_context

    def rejected(self, *, reason):
        self._count("rejected")
        self.rejection_summary[reason] = self.rejection_summary.get(reason, 0) + 1

    def finalize(self, candidate, *, elapsed_ms: int, stop_reason: str, decoder_invocations=None):
        if self._final is not None:
            return deepcopy(self._final)
        duration = max(int(elapsed_ms), self._last_elapsed, 0)
        self._event_index += 1
        point, _context, _valid, _complete = self._snapshot(
            candidate, origin=str(candidate.get("candidate_origin") or "baseline"), verified=True,
            event_index=self._event_index, elapsed_ms=duration)
        last = self._points[-1] if self._points else None
        same_point = last is not None and all(point[key] == last[key] for key in point if key not in ("event_index", "flags"))
        self._remember(last if same_point else point, ["final"])
        sampled, sampling = sample_elapsed_points(self._points, elapsed_ms=duration)
        self.counts["decoder_invocations"] = decoder_invocations
        stages = deepcopy(list(self._stages.values()))
        for stage in stages:
            stage["elapsed_ms"] = max(int(stage["elapsed_ms"]), 0)
        self._final = {"version": PROCESS_EVIDENCE_VERSION, "state": "complete",
                       "source": {"kind": "own_search", "reused_from_candidate_key": None},
                       "objective": deepcopy(self.objective), "elapsed_ms": duration, "stop_reason": stop_reason,
                       "counts": dict(self.counts), "rejection_summary": dict(self.rejection_summary),
                       "sampling": sampling, "points": sampled, "stages": stages}
        self._points.clear()
        self._point_by_event.clear()
        self._pending = self._best_context = self._coverage_context = None
        return deepcopy(self._final)


__all__ = ["OptimizationProcessEvidence", "PROCESS_EVIDENCE_VERSION", "non_search_evidence", "sample_legacy_trace"]

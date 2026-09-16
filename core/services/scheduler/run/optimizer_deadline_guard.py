"""Do not start a decoder after candidate construction consumed its budget."""

import math
from functools import wraps

from .optimizer_attempt_records import evaluate_optional_local_candidate
from .optimizer_search_budget import SearchBudgetExhausted


def observed_decode_seconds(best):
    value = (best or {}).get("initial_decode_runtime_ms", 0.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("initial decode cost must be a finite nonnegative number")
    return float(value) / 1000.0


def prefer_ig_startup(best, *, clock, deadline):
    """A costly incumbent leaves too little time for both another full profile and IG.

    Keep the established small-instance order when no measured cost exists or two
    comparable decodes still fit. This is scheduling admission, not a quality bound.
    """
    if best is None or not best["summary"].success or best["summary"].failed_ops:
        return False
    cost = observed_decode_seconds(best)
    return cost > 0 and 2.0 * cost > max(deadline - clock(), 0.0)


def can_afford_decode(best, *, clock, deadline, search_report_state, phase):
    cost = observed_decode_seconds(best)
    remaining = max(deadline - clock(), 0.0)
    if not cost or cost <= remaining:
        return True
    if search_report_state is not None:
        search_report_state.mark_phase_skipped(phase, "estimated_decode_cost")
        search_report_state.update_candidate_profile(decoder_admission={
            "policy": "observed_initial_decode_cost", "phase": phase,
            "estimated_decode_ms": cost * 1000.0, "remaining_ms": remaining * 1000.0,
        })
    return False


def guard_decoder(schedule_fn, *, clock, deadline, search_report_state, minimum_decode_seconds=0.0):
    if (isinstance(minimum_decode_seconds, bool) or not isinstance(minimum_decode_seconds, (int, float))
            or not math.isfinite(minimum_decode_seconds) or minimum_decode_seconds < 0):
        raise ValueError("minimum decode time must be a finite nonnegative number")
    @wraps(schedule_fn)
    def schedule(*args, **kwargs):
        now = clock()
        if now >= deadline:
            if search_report_state is not None:
                search_report_state.mark_deadline_reached()
            raise SearchBudgetExhausted("candidate_time_budget_reached")
        if minimum_decode_seconds > 0 and now + minimum_decode_seconds > deadline:
            raise SearchBudgetExhausted("estimated_decode_cost")
        return schedule_fn(*args, **kwargs)

    return schedule


def evaluate_optional_local_with_budget(**kwargs):
    try:
        return evaluate_optional_local_candidate(**kwargs)
    except SearchBudgetExhausted:
        # The decoder guard already records the deadline. No candidate was run.
        return None

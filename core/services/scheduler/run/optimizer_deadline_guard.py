"""Do not start a decoder after candidate construction consumed its budget."""

from functools import wraps

from .optimizer_attempt_records import evaluate_optional_local_candidate
from .optimizer_search_budget import SearchBudgetExhausted


def guard_decoder(schedule_fn, *, clock, deadline, search_report_state):
    @wraps(schedule_fn)
    def schedule(*args, **kwargs):
        if clock() >= deadline:
            if search_report_state is not None:
                search_report_state.mark_deadline_reached()
            raise SearchBudgetExhausted("candidate_time_budget_reached")
        return schedule_fn(*args, **kwargs)

    return schedule


def evaluate_optional_local_with_budget(**kwargs):
    try:
        return evaluate_optional_local_candidate(**kwargs)
    except SearchBudgetExhausted:
        # The decoder guard already records the deadline. No candidate was run.
        return None

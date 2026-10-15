"""Attempt-local SGS handoff; formal placement still validates and occupies resources."""

from contextlib import contextmanager
from contextvars import ContextVar

# The SGS witness cache hands the selected candidate's scoring estimate and auto-assign
# resources to formal placement in the same round; it never bypasses placement validation.
_HANDOFF = ContextVar("sgs_score_cache_handoff", default=None)
@contextmanager
def sgs_handoff_scope(handoff):
    token = _HANDOFF.set(handoff)
    try:
        yield
    finally:
        _HANDOFF.reset(token)


def current_sgs_handoff():
    return _HANDOFF.get()


def remember_sgs_estimate(estimate, **inputs):
    handoff = _HANDOFF.get()
    if handoff is not None:
        handoff.remember_estimate(estimate, inputs)


def selected_sgs_estimate(**inputs):
    handoff = _HANDOFF.get()
    return None if handoff is None else handoff.selected_estimate(inputs)


def selected_sgs_resources(op):
    """(machine_id, operator_id) the scoring probe chose for ``op`` this round, or None."""
    handoff = _HANDOFF.get()
    return None if handoff is None else handoff.selected_resources(op)

"""Attempt-local SGS handoff; formal placement still validates and occupies resources."""

from contextlib import contextmanager
from contextvars import ContextVar

_ACTIVE = ContextVar("native_sgs_score_reuse", default=None)
# The SGS witness cache hands the selected candidate's scoring estimate and auto-assign
# resources to formal placement in the same round; it never bypasses placement validation.
_HANDOFF = ContextVar("sgs_score_cache_handoff", default=None)
_CALENDAR_CERTIFICATES = {}
_MULTI_START_CERTIFICATES = {}


def register_multi_start_calendar_certificate(calendar_type, certificate):
    _MULTI_START_CERTIFICATES[calendar_type] = certificate


def native_multi_start_calendar_snapshot(calendar):
    kind = type(calendar)
    if type(kind) is not type:
        return None
    certificate = _MULTI_START_CERTIFICATES.get(kind)
    if certificate is None or vars(kind).get("certified_multi_start_snapshot") is not certificate:
        return None
    if "certified_multi_start_snapshot" in vars(calendar):
        return None
    return certificate(calendar)


def register_sgs_calendar_certificate(calendar_type, certificate):
    _CALENDAR_CERTIFICATES[calendar_type] = certificate


def native_sgs_policy_snapshot(calendar, operator_id):
    kind = type(calendar)
    if type(kind) is not type:
        return None
    certificate = _CALENDAR_CERTIFICATES.get(kind)
    if certificate is None or vars(kind).get("certified_sgs_policy_snapshot") is not certificate:
        return None
    if "certified_sgs_policy_snapshot" in vars(calendar):
        return None
    return certificate(calendar, operator_id)


@contextmanager
def sgs_reuse_scope(reuse):
    token = _ACTIVE.set(reuse)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def current_sgs_reuse():
    return _ACTIVE.get()


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
    reuse = _ACTIVE.get()
    if reuse is not None:
        reuse.remember_estimate(estimate, inputs)
    handoff = _HANDOFF.get()
    if handoff is not None:
        handoff.remember_estimate(estimate, inputs)


def selected_sgs_estimate(**inputs):
    reuse = _ACTIVE.get()
    found = None if reuse is None else reuse.selected_estimate(inputs)
    if found is None:
        handoff = _HANDOFF.get()
        found = None if handoff is None else handoff.selected_estimate(inputs)
    return found


def selected_sgs_resources(op):
    """(machine_id, operator_id) the scoring probe chose for ``op`` this round, or None."""
    handoff = _HANDOFF.get()
    return None if handoff is None else handoff.selected_resources(op)

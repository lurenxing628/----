"""Attempt-local SGS handoff; formal placement still validates and occupies resources."""

from contextlib import contextmanager
from contextvars import ContextVar

_ACTIVE = ContextVar("native_sgs_score_reuse", default=None)
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


def remember_sgs_estimate(estimate, **inputs):
    reuse = _ACTIVE.get()
    if reuse is not None:
        reuse.remember_estimate(estimate, inputs)


def selected_sgs_estimate(**inputs):
    reuse = _ACTIVE.get()
    return None if reuse is None else reuse.selected_estimate(inputs)

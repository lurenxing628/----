"""Fast identity proof for unchanged native timing methods, without bound lookups."""

from core.algorithm_runtime.calendar_timing_memo import member_identity_guard

from .calendar_engine import NATIVE_TIMING_METHODS, CalendarEngine

_SERVICE_METHODS = ("get_efficiency", "adjust_to_working_time", "add_working_hours")
_ENGINE_METHODS = _SERVICE_METHODS + ("policy_for_datetime", "_policy_for_datetime", "_policy_for_date")
_ATTRIBUTE_HOOKS = ("__getattribute__", "__getattr__", "__dict__")
_MEMO_SERVICE_METHODS = _SERVICE_METHODS + ("certified_slot_window",)


def _make_guard(service_type, service_methods, engine_methods):
    service_unchanged = member_identity_guard(service_type, service_methods + _ATTRIBUTE_HOOKS + ("_engine",))
    engine_unchanged = member_identity_guard(CalendarEngine, engine_methods + _ATTRIBUTE_HOOKS)

    def supported(service):
        if type(service) is not service_type or not service_unchanged():
            return False
        data = service.__dict__
        engine = data.get("_engine")
        return (type(engine) is CalendarEngine and engine_unchanged()
                and data.keys().isdisjoint(service_methods)
                and engine.__dict__.keys().isdisjoint(engine_methods))

    return supported


def make_native_method_guard(service_type):
    return _make_guard(service_type, _SERVICE_METHODS, _ENGINE_METHODS)


def make_timing_memo_guard(service_type):
    """The certificate guard plus the certificate method itself, which the per-decode memo also answers."""
    return _make_guard(service_type, _MEMO_SERVICE_METHODS, NATIVE_TIMING_METHODS)

"""Fast identity proof for unchanged native timing methods, without bound lookups."""

import operator

from .calendar_engine import CalendarEngine

_SERVICE_METHODS = ("get_efficiency", "adjust_to_working_time", "add_working_hours")
_ENGINE_METHODS = _SERVICE_METHODS + ("policy_for_datetime", "_policy_for_datetime", "_policy_for_date")
_ATTRIBUTE_HOOKS = ("__getattribute__", "__getattr__", "__dict__")


def _member_guard(cls, names):
    original = tuple(map(cls.__dict__.get, names))
    lineage = cls.__mro__

    def unchanged():
        return cls.__mro__ is lineage and all(map(operator.is_, map(cls.__dict__.get, names), original))

    return unchanged


def make_native_method_guard(service_type):
    service_unchanged = _member_guard(service_type, _SERVICE_METHODS + _ATTRIBUTE_HOOKS + ("_engine",))
    engine_unchanged = _member_guard(CalendarEngine, _ENGINE_METHODS + _ATTRIBUTE_HOOKS)

    def supported(service):
        if type(service) is not service_type or not service_unchanged():
            return False
        data = service.__dict__
        engine = data.get("_engine")
        return (type(engine) is CalendarEngine and engine_unchanged()
                and data.keys().isdisjoint(_SERVICE_METHODS)
                and engine.__dict__.keys().isdisjoint(_ENGINE_METHODS))

    return supported

"""Exact, side-effect-free content certificates for native scheduling inputs."""

import math
import operator
from datetime import date, datetime, time
from typing import Any

UNSUPPORTED = object()
_SCALARS = (type(None), bool, int, str, date, datetime, time)
_RECORD_SCALARS = frozenset(_SCALARS + (float,))


def scalar_tuple_snapshot(values, previous=None) -> Any:
    if previous is not None and len(values) == len(previous[0]) and all(map(operator.is_, values, previous[0])):
        # Every previous element was proved to be an exact immutable native scalar.
        return previous
    kinds = tuple(map(type, values))
    if any(type(kind) is not type for kind in kinds) or not set(kinds).issubset(_RECORD_SCALARS):
        return UNSUPPORTED
    for value, kind in zip(values, kinds):
        if (kind is float and not math.isfinite(value)) or (kind in (datetime, time) and value.tzinfo is not None):
            return UNSUPPORTED
    return values, kinds


def scalar_snapshot(value) -> Any:
    kind = type(value)
    if type(kind) is not type:
        return UNSUPPORTED
    if kind in _SCALARS:
        if kind in (datetime, time) and value.tzinfo is not None:
            return UNSUPPORTED
        return kind, value
    if kind is float and math.isfinite(value):
        return kind, value
    return UNSUPPORTED


def content_snapshot(value, _depth=0) -> Any:
    scalar = scalar_snapshot(value)
    if scalar is not UNSUPPORTED:
        return scalar
    kind = type(value)
    if type(kind) is not type or kind not in (dict, list, tuple, set, frozenset) or _depth > 12:
        return UNSUPPORTED
    if kind is dict:
        items = [(content_snapshot(key, _depth + 1), content_snapshot(item, _depth + 1)) for key, item in value.items()]
        if any(key is UNSUPPORTED or item is UNSUPPORTED for key, item in items):
            return UNSUPPORTED
        return kind, frozenset(items)
    items = [content_snapshot(item, _depth + 1) for item in value]
    if any(item is UNSUPPORTED for item in items):
        return UNSUPPORTED
    return kind, frozenset(items) if kind in (set, frozenset) else tuple(items)


def native_record_snapshot(record, allowed_types) -> Any:
    record_type = type(record)
    if type(record_type) is not type or record_type not in allowed_types:
        return UNSUPPORTED
    data = vars(record)
    items = tuple(data.items())
    kinds = tuple(map(type, data.values()))
    if (any(type(kind) is not type for kind in kinds) or not set(kinds).issubset(_RECORD_SCALARS)
            or any(type(key) is not str for key, _ in items)):
        return UNSUPPORTED
    for (_, value), kind in zip(items, kinds):
        if (kind is float and not math.isfinite(value)) or (kind in (datetime, time) and value.tzinfo is not None):
            return UNSUPPORTED
    return type(record), items, kinds


def make_class_guard(cls):
    """Capture original descriptors, including attribute hooks and inheritance."""
    lineage = cls.__mro__
    layers = [(base, tuple(vars(base)), tuple(vars(base).values())) for base in lineage if base.__module__ != "builtins"]
    shadowed = frozenset(key for base in lineage for key, value in vars(base).items()
                        if callable(value) or isinstance(value, (property, staticmethod, classmethod))
                        or key in ("__getattribute__", "__getattr__", "__dict__"))

    def supported(instance):
        if type(instance) is not cls or cls.__mro__ is not lineage:
            return False
        for base, keys, values in layers:
            current = vars(base)
            # copyreg lazily records [] when deepcopy first visits a non-slotted DTO.
            if "__slotnames__" not in keys and type(current.get("__slotnames__")) is list and not current["__slotnames__"]:
                current = {key: value for key, value in current.items() if key != "__slotnames__"}
            if tuple(current) != keys or not all(map(operator.is_, current.values(), values)):
                return False
        return vars(instance).keys().isdisjoint(shadowed)

    return supported
